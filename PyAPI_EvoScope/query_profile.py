import pickle
import json
import os
import sys
from collections import Counter

# 确保可以导入 aggregate_API_profile 中的类
try:
    from aggregate_API_profile import *
except ImportError:
    # 如果导入失败，动态执行模块代码
    try:
        with open('aggregate_API_profile.py', 'r', encoding='utf-8') as f:
            exec(f.read(), globals())
        print("✓ 动态加载类定义成功")
    except Exception as e:
        print(f"✗ 无法加载类定义: {e}")
        sys.exit(1)


def get_all_APIs(pf_tree):
    """获取所有 API 列表"""
    all_nodes_list = all_nodes(pf_tree)
    api_nodes = []
    api_list = []
    for node in all_nodes_list:
        if isinstance(node, AggeragatedAPINode) or isinstance(node, AggeragatedAPIAliasNode):
            api_nodes.append(node)
            api_list.append(node.full_name)
    return api_list, api_nodes


def get_all_classes(pf_tree):
    """获取所有类"""
    all_nodes_list = all_nodes(pf_tree)
    classes = []
    class_nodes = []
    for node in all_nodes_list:
        if isinstance(node, AggeragatedClassNode) or isinstance(node, AggeragatedClassAliasNode):
            classes.append(node.full_name)
            class_nodes.append(node)
    return classes, class_nodes


def print_basic_stats(pf_tree):
    """打印基本统计信息"""
    print("\n" + "=" * 60)
    print("  基本统计信息")
    print("=" * 60)

    all_nodes_list = all_nodes(pf_tree)

    # 统计不同类型节点
    node_types = Counter(type(node).__name__ for node in all_nodes_list)

    print(f"\n总节点数: {len(all_nodes_list)}")
    print("\n节点类型分布:")
    for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {node_type}: {count}")

    # 获取库信息
    if hasattr(pf_tree, 'name'):
        print(f"\n库名: {pf_tree.name}")

    if hasattr(pf_tree, 'full_name'):
        print(f"完整名称: {pf_tree.full_name}")

    if hasattr(pf_tree, 'available_versions'):
        versions = pf_tree.available_versions
        print(f"\n分析版本数: {len(versions)}")
        if versions:
            print(f"版本范围: {min(versions)} → {max(versions)}")
            print(f"所有版本: {', '.join(sorted(versions))}")


def print_api_details(pf_tree, max_apis=10):
    """打印API详情"""
    print("\n" + "=" * 60)
    print("  API 详情")
    print("=" * 60)

    api_list, api_nodes = get_all_APIs(pf_tree)

    print(f"\n总共找到 {len(api_list)} 个 API")

    if api_list:
        print(f"\n前 {min(max_apis, len(api_list))} 个 API:")
        for i, (api_name, api_node) in enumerate(zip(api_list[:max_apis], api_nodes[:max_apis]), 1):
            print(f"\n{i:2}. {api_name}")

            # 显示API类型
            node_type = type(api_node).__name__
            print(f"   类型: {node_type}")

            # 显示可用版本
            if hasattr(api_node, 'available_versions'):
                versions = api_node.available_versions
                print(f"   可用版本: {len(versions)} 个")
                if versions:
                    print(f"   版本: {', '.join(sorted(versions))}")

            # 如果是API别名，显示真实API
            if isinstance(api_node, AggeragatedAPIAliasNode) and hasattr(api_node, 'real_API'):
                real_apis = api_node.real_API
                if real_apis:
                    first_version = list(real_apis.keys())[0]
                    real_api = real_apis[first_version]
                    if hasattr(real_api, 'full_name'):
                        print(f"   真实API: {real_api.full_name}")

            # 如果是APINode，显示参数信息
            if isinstance(api_node, AggeragatedAPINode):
                if hasattr(api_node, 'kws') and api_node.kws:
                    print(f"   参数历史:")
                    for version, params in api_node.kws.items():
                        print(f"     {version}: {params}")

                if hasattr(api_node, 'source') and api_node.source:
                    print(f"   源码文件: {len(api_node.source)} 个版本")


def print_class_details(pf_tree, max_classes=5):
    """打印类详情"""
    print("\n" + "=" * 60)
    print("  类详情")
    print("=" * 60)

    class_list, class_nodes = get_all_classes(pf_tree)

    print(f"\n总共找到 {len(class_list)} 个类")

    if class_list:
        print(f"\n前 {min(max_classes, len(class_list))} 个类:")
        for i, (class_name, class_node) in enumerate(zip(class_list[:max_classes], class_nodes[:max_classes]), 1):
            print(f"\n{i:2}. {class_name}")

            # 显示类类型
            node_type = type(class_node).__name__
            print(f"   类型: {node_type}")

            # 显示可用版本
            if hasattr(class_node, 'available_versions'):
                versions = class_node.available_versions
                print(f"   可用版本: {len(versions)} 个")

            # 显示子节点（方法）
            if hasattr(class_node, 'children'):
                method_count = len(class_node.children)
                print(f"   方法数量: {method_count}")

                if method_count > 0:
                    print(f"   方法示例:")
                    for j, method in enumerate(class_node.children[:3], 1):
                        if hasattr(method, 'full_name'):
                            print(f"     - {method.full_name}")

            # 如果是类别名，显示真实类
            if isinstance(class_node, AggeragatedClassAliasNode) and hasattr(class_node, 'real_class'):
                real_classes = class_node.real_class
                if real_classes:
                    first_version = list(real_classes.keys())[0]
                    real_class = real_classes[first_version]
                    if hasattr(real_class, 'full_name'):
                        print(f"   真实类: {real_class.full_name}")


def find_api_changes(pf_tree):
    """查找有变化的API"""
    print("\n" + "=" * 60)
    print("API 变化分析")
    print("=" * 60)

    all_nodes_list = all_nodes(pf_tree)
    changed_apis = []

    for node in all_nodes_list:
        # 检查APINode的参数变化
        if isinstance(node, AggeragatedAPINode) and hasattr(node, 'kws'):
            param_sets = list(node.kws.values())

            # 检查是否有参数变化
            if len(set(tuple(p) for p in param_sets)) > 1:
                changed_apis.append({
                    'api': node.full_name,
                    'param_history': node.kws,
                    'versions': node.available_versions
                })

    if changed_apis:
        print(f"\n找到 {len(changed_apis)} 个有参数变化的API:")
        for i, api_info in enumerate(changed_apis[:5], 1):  # 只显示前5个
            print(f"\n{i}. {api_info['api']}")
            print(f"   版本: {', '.join(sorted(api_info['versions']))}")

            # 显示参数变化
            param_history = api_info['param_history']
            versions = sorted(param_history.keys())

            if len(versions) > 1:
                print(f"   参数变化历史:")
                for j in range(len(versions) - 1):
                    v1 = versions[j]
                    v2 = versions[j + 1]
                    params1 = param_history.get(v1, [])
                    params2 = param_history.get(v2, [])

                    if params1 != params2:
                        added = list(set(params2) - set(params1))
                        removed = list(set(params1) - set(params2))

                        if added or removed:
                            changes = []
                            if added:
                                changes.append(f"新增: {', '.join(added)}")
                            if removed:
                                changes.append(f"移除: {', '.join(removed)}")
                            print(f"     {v1} → {v2}: {'; '.join(changes)}")
    else:
        print("\n未找到有参数变化的API")


def export_to_json(pf_tree, lib_name):
    """导出为JSON文件"""
    print("\n" + "=" * 60)
    print("导出数据")
    print("=" * 60)

    def serialize_node(node):
        """序列化单个节点"""
        result = {
            'type': type(node).__name__,
        }

        # 添加基本属性
        basic_attrs = ['name', 'full_name', 'available_versions']
        for attr in basic_attrs:
            if hasattr(node, attr):
                result[attr] = getattr(node, attr)

        # 特殊处理
        if isinstance(node, AggeragatedAPINode):
            if hasattr(node, 'kws'):
                result['parameters'] = node.kws
            if hasattr(node, 'default_values'):
                result['default_values'] = node.default_values

        elif isinstance(node, AggeragatedAPIAliasNode) and hasattr(node, 'real_API'):
            real_apis = {}
            for version, real_api in node.real_API.items():
                if hasattr(real_api, 'full_name'):
                    real_apis[version] = real_api.full_name
            result['real_API'] = real_apis

        elif isinstance(node, AggeragatedClassAliasNode) and hasattr(node, 'real_class'):
            real_classes = {}
            for version, real_class in node.real_class.items():
                if hasattr(real_class, 'full_name'):
                    real_classes[version] = real_class.full_name
            result['real_class'] = real_classes

        return result

    try:
        # 构建导出数据
        export_data = {
            'library': lib_name,
            'tree': serialize_node(pf_tree),
            'summary': {
                'total_nodes': len(all_nodes(pf_tree)),
                'api_count': len(get_all_APIs(pf_tree)[0]),
                'class_count': len(get_all_classes(pf_tree)[0])

            },
            'sample_apis': get_all_APIs(pf_tree)[:50],
            'sample_class': get_all_APIs(pf_tree)[:20]
        }

        # 保存文件
        filename = f"./output_analysis/{lib_name}_analysis.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n✓ 数据已导出到: {filename}")

        # 显示文件大小
        size_kb = os.path.getsize(filename) / 1024
        print(f"文件大小: {size_kb:.1f} KB")

    except Exception as e:
        print(f"\n✗ 导出失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("PyMevol API 查询工具")
    print("=" * 60)

    # 1. 检查输出目录
    if not os.path.exists('output_agg'):
        print("\nerror: output_agg 目录不存在")
        print("\n请先运行以下命令生成数据:")
        print("1. python generate_API_profile.py ./pypi_libs/ ./output_profile/ ./output_agg/")
        print("2. python aggregate_API_profile.py")
        return

    # 2. 查找可用的库
    lib_files = [f for f in os.listdir('output_agg') if f.endswith('.pickle')]

    if not lib_files:
        print("\nerror: 未找到聚合剖面文件")
        print("\n请先运行:")
        print("  python aggregate_API_profile.py")
        return

    print(f"\n 找到 {len(lib_files)} 个库:")
    for i, file in enumerate(lib_files, 1):
        lib_name = file.replace('.pickle', '')
        print(f"  {i}. {lib_name}")

    # 3. 加载第一个库
    first_lib = lib_files[0].replace('.pickle', '')
    print(f"\n 正在分析: {first_lib}")

    try:
        with open(f'output_agg/{first_lib}.pickle', 'rb') as f:
            pf_tree = pickle.load(f)

        print("✓ 数据加载成功")

        # 4. 显示各种信息
        print_basic_stats(pf_tree)
        print_api_details(pf_tree, max_apis=5)
        print_class_details(pf_tree, max_classes=3)
        find_api_changes(pf_tree)

        # 5. 导出数据
        export = input("\n是否导出为JSON文件? (y/n): ").strip().lower()
        if export == 'y':
            export_to_json(pf_tree, first_lib)

        print(f"\n {first_lib} 分析完成！")

    except Exception as e:
        print(f"\n 加载失败: {e}")
        print("\n可能的解决方案:")
        print("1. 确保已经运行了 aggregate_API_profile.py")
        print("2. 检查 pickle 文件是否完整")
        print("3. 尝试重新生成数据")


if __name__ == "__main__":
    main()