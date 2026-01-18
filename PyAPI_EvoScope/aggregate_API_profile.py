import json
import os
import shutil
import glob
from packaging import version
import packaging
import copy
import pickle
from generate_API_profile import *
from collections import OrderedDict
import difflib

class AggeragatedModuleOrPackageNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.children = []
        self.parent = None
        self.available_versions=[]
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class AggeragatedClassNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.children = []
        self.aliases = OrderedDict()
        self.available_versions = []
        self.source=OrderedDict()
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class AggeragatedClassAliasNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.children = []
        self.real_class = OrderedDict()
        self.available_versions = []
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class AggeragatedAPINode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.source = OrderedDict()
        self.aliases = OrderedDict()
        self.ast = None
        self.kws={}
        self.default_values=OrderedDict()
        self.available_versions = []
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))


class AggeragatedAPIAliasNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.real_API = OrderedDict()
        self.available_versions = []
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))


def aggregate_deprecation_history(lib_name, output_dir, output_dir_aggregate):
    #with open(os.path.join(output_dir, "package_lib_map.json"), 'r') as f:
        #API_dict = json.load(f)
    API_dict = {}
    for file in glob.glob(os.path.join(output_dir, "{}*.json".format(lib_name))):
        print(file)
        with open(file, 'r') as f:
            deprecation_dict = json.load(f)
        for key in deprecation_dict:
            if key not in API_dict:
                API_dict[key] = deprecation_dict[key]
    if len(API_dict)>0:
        with open(os.path.join(output_dir_aggregate, "{}.json".format(lib_name)), 'w') as f:
            f.write(json.dumps(API_dict))


def create_new_agg_tree(pf_tree,version):
    agg_tree = AggeragatedModuleOrPackageNode(pf_tree.name)
    agg_tree.available_versions.append(version)

    pf_agg_node_dict={}

    pf_leaf_stack = []
    pf_working_queue = []
    pf_working_queue.append(pf_tree)

    # bfs to search all I leafs
    while len(pf_working_queue) > 0:
        tmp_node = pf_working_queue.pop(0)
        pf_leaf_stack.append(tmp_node)
        if hasattr(tmp_node, "children"):
            pf_working_queue.extend(tmp_node.children)
    for node in pf_leaf_stack[::-1]:
        if isinstance(node,ModuleOrPackageNode):
            agg_node = AggeragatedModuleOrPackageNode(node.name)
            agg_node.full_name=node.full_name
            agg_node.available_versions.append(version)
        if isinstance(node,APIAliasNode):
            agg_node = AggeragatedAPIAliasNode(node.name)
            agg_node.available_versions.append(version)
            agg_node.full_name=node.full_name
        if isinstance(node,APINode):
            agg_node = AggeragatedAPINode(node.name)
            agg_node.available_versions.append(version)
            agg_node.full_name = node.full_name
            agg_node.kws[version]=node.kws
            agg_node.source[version]={"no_diff":-1,"source":node.source}
            agg_node.default_values[version]=node.default_values
        if isinstance(node,ClassNode):
            agg_node = AggeragatedClassNode(node.name)
            agg_node.available_versions.append(version)
            agg_node.full_name = node.full_name
            agg_node.source[version] = {"no_diff": -1, "source": node.source}
        if isinstance(node,ClassAliasNode):
            agg_node = AggeragatedClassAliasNode(node.name)
            agg_node.available_versions.append(version)
            agg_node.full_name = node.full_name
        pf_agg_node_dict[node] = agg_node

    for node in pf_leaf_stack[::-1]:
        agg_node = pf_agg_node_dict[node]
        if hasattr(node,"parent"):
            #print(node.parent.full_name)
            if node.parent:
                agg_node.parent = pf_agg_node_dict[node.parent]
            else:
                agg_node.parent = None
        if hasattr(node,"children"):
            for child in node.children:
                agg_node.children.append(pf_agg_node_dict[child])
        if hasattr(node,"real_API"):
            agg_node.real_API[version] = pf_agg_node_dict[node.real_API]
        if hasattr(node,"real_class"):
            agg_node.real_class[version] = pf_agg_node_dict[node.real_class]
        if hasattr(node, "aliases"):
            if version not in agg_node.aliases:
                agg_node.aliases[version]=set()
            for alias in node.aliases:
                agg_node.aliases[version].add(pf_agg_node_dict[alias])
    return pf_agg_node_dict[pf_tree]
    #construct_agg_tree_recursive(agg_tree,pf_tree,version)


def all_nodes(root_node):
    pf_leaf_stack = []
    pf_working_queue = []
    pf_working_queue.append(root_node)

    # bfs to search all I leafs
    while len(pf_working_queue) > 0:
        tmp_node = pf_working_queue.pop(0)
        pf_leaf_stack.append(tmp_node)
        if hasattr(tmp_node, "children"):
            pf_working_queue.extend(tmp_node.children)
    return pf_leaf_stack

def add_tree_to_agg_tree(pf_tree, pf_agg_tree,version):
    new_agg_tree = create_new_agg_tree(pf_tree,version)
    #pf_agg_tree.available_versions.append(version)
    new_leaf_stack = all_nodes(new_agg_tree)
    old_leaf_stack = all_nodes(pf_agg_tree)
    old_table = OrderedDict()
    new_table = OrderedDict()
    for old_node in old_leaf_stack:
        if isinstance(old_node,AggeragatedClassNode):
            old_table[(old_node.full_name,"class")]=old_node
        elif isinstance(old_node,AggeragatedClassAliasNode):
            old_table[(old_node.full_name, "class_alias")] = old_node
        elif isinstance(old_node,AggeragatedModuleOrPackageNode):
            old_table[old_node.full_name]=old_node
        elif isinstance(old_node,AggeragatedAPINode):
            old_table[(old_node.full_name,"api")] = old_node
        else:
            old_table[(old_node.full_name, "api_alias")] = old_node
    for new_node in new_leaf_stack:
        if isinstance(new_node,AggeragatedClassNode):
            new_table[(new_node.full_name,"class")]=new_node
        elif isinstance(new_node,AggeragatedClassAliasNode):
            new_table[(new_node.full_name, "class_alias")] = new_node
        elif isinstance(new_node,AggeragatedModuleOrPackageNode):
            new_table[new_node.full_name]=new_node
        elif isinstance(new_node, AggeragatedAPINode):
            new_table[(new_node.full_name, "api")] = new_node
        else:
            new_table[(new_node.full_name, "api_alias")] = new_node
    for new_node in new_leaf_stack:
        if hasattr(new_node, "real_API"):
            for version in new_node.real_API:
                new_node.real_API[version]=new_node.real_API[version].full_name
        if hasattr(new_node, "real_class"):
            for version in new_node.real_class:
                new_node.real_class[version]=new_node.real_class[version].full_name
        if hasattr(new_node, "aliases"):
            for version in new_node.aliases:
                new_set = set()
                for alias in new_node.aliases[version]:
                    new_set.add(alias.full_name)
                new_node.aliases[version]=new_set

    not_exist_nodes = [key for key in new_table if key not in old_table]
    already_exist_nodes = [key for key in new_table if key in old_table]
    for key in not_exist_nodes:
        n = new_table[key]
        add_new_node_to_agg_tree(n, pf_agg_tree)
    for key in already_exist_nodes:
        n = new_table[key]
        n_old = old_table[key]
        n_old.available_versions.append(n.available_versions[0])
        if hasattr(n_old, "kws"):
            for key in n.kws:
                n_old.kws[key] = n.kws[key]
        if hasattr(n_old, "default_values"):
            for key in n.default_values:
                n_old.default_values[key] = n.default_values[key]
        if hasattr(n_old, "source"):
            last_value = list(n_old.source.items())[-1]
            new_value = list(n.source.items())[-1]
            last_src_file = last_value[1]["source"]
            new_src_file = new_value[1]["source"]
            if last_src_file=="":
                last_src_lines=[]
            else:
                with open(last_src_file,"r") as f:
                    last_src_lines = f.readlines()
            if new_src_file == "":
                new_src_lines=[]
            else:
                with open(new_src_file,"r") as f:
                    new_src_lines = f.readlines()
            diff_list=[]
            for line in difflib.unified_diff(last_src_lines, new_src_lines, fromfile='file1', tofile='file2', n=0):
                for prefix in ('---', '+++', '@@'):
                    if line.startswith(prefix):
                        break
                else:
                    diff_list.append(line)
            new_value[1]["no_diff"]=len(diff_list)
            n_old.source[new_value[0]]=new_value[1]
        if hasattr(n_old,"real_API"):
            for key in n.real_API:
                n_old.real_API[key]=n.real_API[key]
        if hasattr(n_old,"real_class"):
            for key in n.real_class:
                n_old.real_class[key]=n.real_class[key]
        if hasattr(n_old,"aliases"):
            for key in n.aliases:
                n_old.aliases[key]=n.aliases[key]

    # connect

    new_all_nodes = all_nodes(pf_agg_tree)
    for node in new_all_nodes:
        if hasattr(node,"real_API"):
            for key in node.real_API:
                dst = node.real_API[key]
                if isinstance(dst,str):
                    if (dst,"api") in old_table:
                        r_dst = old_table[(dst,"api")]
                    else:
                        r_dst = new_table[(dst, "api")]
                    node.real_API[key]=r_dst
        if hasattr(node,"real_class"):
            for key in node.real_class:
                dst = node.real_class[key]
                if isinstance(dst,str):
                    if (dst,"class") in old_table:
                        r_dst = old_table[(dst,"class")]
                    else:
                        r_dst = new_table[(dst, "class")]
                    node.real_class[key]=r_dst
        if hasattr(node,"aliases"):
            if isinstance(node,AggeragatedAPINode):
                for key in node.aliases:
                    new_set = set()
                    for dst in node.aliases[key]:
                        if isinstance(dst,str):
                            if (dst, "api_alias") in old_table:
                                r_dst = old_table[(dst, "api_alias")]
                            else:
                                r_dst = new_table[(dst, "api_alias")]
                            new_set.add(r_dst)
                        else:
                            new_set.add(dst)
                    node.aliases[key]=new_set
            elif isinstance(node, AggeragatedClassNode):
                for key in node.aliases:
                    new_set = set()
                    for dst in node.aliases[key]:
                        if isinstance(dst,str):
                            if (dst, "class_alias") in old_table:
                                r_dst = old_table[(dst, "class_alias")]
                            else:
                                r_dst = new_table[(dst, "class_alias")]
                            new_set.add(r_dst)
                        else:
                            new_set.add(dst)
                    node.aliases[key]=new_set






    #for node in pf_leaf_stack:
        #add_node_to_agg_tree(node,pf_agg_tree,version)


def add_new_node_to_agg_tree(node,pf_agg_tree):
    API_full = node.full_name
    access_path_list = API_full.split(".")
    tmp_node = pf_agg_tree
    ind = None
    for i in access_path_list[1:]:
        child_name_list = []
        for child in tmp_node.children:
            child_name_list.append(child.name)
        if i in child_name_list:
            tmp_node = tmp_node.children[child_name_list.index(i)]
        else:
            ind = access_path_list.index(i)
            break
    if ind:
        sliced_path = access_path_list[ind:]
        tmp = node
        for i in range(len(sliced_path) - 1):
            tmp = tmp.parent
        tmp_node.children.append(tmp)

def add_node_to_agg_tree(node,pf_agg_tree,version):
    API_full = node.full_name
    access_path_list = API_full.split(".")
    tmp_node = pf_agg_tree
    for i in access_path_list[1:]:
        pas = False
        for child in tmp_node.children:
            if child.name == i:
                tmp_node = child
                pas = True
                break
        if not pas:
            # create the node
            node = merge_branch_in_agg_tree(node,pf_agg_tree,version)
            return node
    if isinstance(node, AggeragatedAPIAliasNode) and isinstance(tmp_node, AggeragatedClassAliasNode) or \
            isinstance(node, AggeragatedAPINode) and isinstance(tmp_node, AggeragatedClassNode):
        raise_except = True
        for child in tmp_node.children:
            if child.name == tmp_node.name:
                tmp_node=child
                raise_except = False
                break
        if raise_except:
            raise Exception("missing node")
    # else add info
    if version in tmp_node.available_versions:
        return tmp_node
    if isinstance(tmp_node,AggeragatedModuleOrPackageNode):
        tmp_node.available_versions.append(version)
    if isinstance(tmp_node,AggeragatedAPINode):
        tmp_node.available_versions.append(version)
    if isinstance(tmp_node,AggeragatedClassNode):
        tmp_node.available_versions.append(version)
    if isinstance(tmp_node,AggeragatedAPIAliasNode):
        tmp_node.available_versions.append(version)
        dst_node = go_to_api_node_from_root(pf_agg_tree,node.real_API[version].full_name)
        if not dst_node:
            dst_node = add_node_to_agg_tree(node.real_API[version],pf_agg_tree,version)
        tmp_node.real_API[version]=dst_node
        try:
            if version not in dst_node.aliases:
                dst_node.aliases[version]=set()
        except Exception:
            print("g")
        dst_node.aliases[version].add(tmp_node)
    if isinstance(tmp_node,AggeragatedClassAliasNode):
        tmp_node.available_versions.append(version)
        dst_node = go_to_api_node_from_root(pf_agg_tree,node.real_class[version].full_name)
        if not dst_node:
            dst_node = add_node_to_agg_tree(node.real_class[version],pf_agg_tree,version)
        tmp_node.real_class[version]=dst_node
        if version not in dst_node.aliases:
            dst_node.aliases[version]=set()
        dst_node.aliases[version].add(tmp_node)

    return tmp_node


def merge_branch_in_agg_tree(node,pf_agg_tree,version):
    API_full = node.full_name
    access_path_list = API_full.split(".")
    tmp_node = pf_agg_tree
    ind = None
    for i in access_path_list[1:]:
        child_name_list = []
        for child in tmp_node.children:
            child_name_list.append(child.name)
        if i in child_name_list:
            tmp_node = tmp_node.children[child_name_list.index(i)]
        else:
            ind = access_path_list.index(i)
            break
    if ind:
        sliced_path = access_path_list[ind:]
        tmp = node
        for i in range(len(sliced_path)-1):
            tmp = tmp.parent
        tmp_node.children.append(tmp)
        leaf_list = all_nodes(tmp)
        for node2 in leaf_list:
            if hasattr(node2,"real_API"):
                new_node = add_node_to_agg_tree(node2.real_API[version],pf_agg_tree,version)
                node2.real_API[version]=new_node
                to_be_removed = None
                if version in new_node.aliases:
                    for alias in new_node.aliases[version]:
                        if alias.full_name == node2.full_name:
                            to_be_removed = alias
                            break
                    if to_be_removed:
                        new_node.aliases[version].remove(to_be_removed)
                    new_node.aliases[version].add(node2)
                continue
            if hasattr(node2,"real_class"):
                new_node = add_node_to_agg_tree(node2.real_class[version],pf_agg_tree,version)
                node2.real_class[version] = new_node
                to_be_removed=None
                if version in new_node.aliases:
                    for alias in new_node.aliases[version]:
                        if alias.full_name == node2.full_name:
                            to_be_removed=alias
                            break
                    if to_be_removed:
                        new_node.aliases[version].remove(to_be_removed)
                    new_node.aliases[version].add(node2)
                continue

            if hasattr(node2,"aliases"):
                copy_set = set([i for i in node2.aliases[version]])
                for alias in copy_set:
                    new_node = add_node_to_agg_tree(alias, pf_agg_tree, version)
                    node2.aliases[version].remove(alias)
                    node2.aliases[version].add(new_node)
                    if hasattr(new_node, "real_API"):
                        new_node.real_API[version]=node2
                    if hasattr(new_node, "real_class"):
                        new_node.real_class[version]=node2
    return node



def construct_agg_tree_recursive(agg_node,pf_node,version):
    for child in pf_node.children:
        if isinstance(child,ModuleOrPackageNode):
            agg_child = AggeragatedModuleOrPackageNode(child.name)
            agg_child.available_versions.append(version)
            agg_child.parent=agg_node
            agg_node.children.append(agg_child)
            construct_agg_tree_recursive(agg_child,child,version)
        if isinstance(child,APIAliasNode):
            agg_child = AggeragatedAPIAliasNode(child.name)
            agg_child.available_versions.append(version)
            agg_child.parent = agg_node
            agg_node.children.append(agg_child)
            construct_agg_tree_recursive(agg_child, child, version)



def aggregate_profile(lib_name, output_dir, output_dir_aggregate):
    if os.path.exists(os.path.join(output_dir_aggregate, "{}.pickle".format(lib_name))):
        print("skip {}", lib_name)
        return
    versions = os.listdir(os.path.join(os.path.join(output_dir, lib_name)))
    versions.sort(key=lambda x: packaging.version.Version(x))
    #versions = ["2.0.0","2.5.1"]
    count = 0
    removed_dict = {}
    rapi_count_dict = {}
    count_none = 0
    count_notnone = 0
    pf_agg_dict = {}
    for version in versions:
        output_v_dir = os.path.join(os.path.join(output_dir, lib_name), version)
        if not os.path.exists(output_v_dir):
            continue
        file_list = glob.glob(os.path.join(output_v_dir, "*.pickle"))
        for file in file_list:
            with open(file, 'rb') as f:
                pf_tree = pickle.load(f)
            if pf_tree.name not in pf_agg_dict:
                pf_agg_dict[pf_tree.name]=create_new_agg_tree(pf_tree,version)
            else:
                pf_agg_tree= pf_agg_dict[pf_tree.name]
                add_tree_to_agg_tree(pf_tree, pf_agg_tree,version)

    for pkg in pf_agg_dict:
        with open(os.path.join(output_dir_aggregate, "{}.pickle".format(pkg)), 'wb') as f:
            pickle.dump(pf_agg_dict[pkg], f, pickle.HIGHEST_PROTOCOL)



def main():
    with open("./lib_names.txt") as f:
        lib_list = ["requests"]
    output_dir = "./output_profile"
    output_dir_aggregate = "./output_agg"
    for lib in lib_list:
        aggregate_profile(lib, output_dir, output_dir_aggregate)
if __name__ == '__main__':
    main()