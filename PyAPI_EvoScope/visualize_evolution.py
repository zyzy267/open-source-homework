import pickle
import os
import numpy as np
import pandas as pd
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from matplotlib.patches import Rectangle
import json

# 设置样式
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class GenericNode:
    """通用节点类"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class CustomUnpickler(pickle.Unpickler):
    """自定义Unpickler"""

    def find_class(self, module, name):
        if module == '__main__' or module.startswith('aggregate_API_profile'):
            class_dict = {
                'AggeragatedModuleOrPackageNode': GenericNode,
                'AggeragatedClassNode': GenericNode,
                'AggeragatedClassAliasNode': GenericNode,
                'AggeragatedAPINode': GenericNode,
                'AggeragatedAPIAliasNode': GenericNode,
                'ModuleOrPackageNode': GenericNode,
                'ClassNode': GenericNode,
                'ClassAliasNode': GenericNode,
                'APINode': GenericNode,
                'APIAliasNode': GenericNode,
                'OrderedDict': dict
            }
            if name in class_dict:
                return class_dict[name]

        try:
            return super().find_class(module, name)
        except:
            return GenericNode


def load_pickle_file(filepath):
    """加载pickle文件"""
    with open(filepath, 'rb') as f:
        unpickler = CustomUnpickler(f)
        return unpickler.load()


class NumpyEncoder(json.JSONEncoder):
    """处理numpy类型的JSON编码器"""

    def default(self, obj):
        if isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        return super().default(obj)


def extract_simple_tree_data(node, depth=0, path=""):
    """提取简化的树形数据"""
    data = []

    node_name = getattr(node, 'name', 'Unknown')
    node_info = {
        'name': node_name,
        'depth': int(depth),  # 确保是Python int
        'path': f"{path}.{node_name}" if path else node_name,
        'has_children': False
    }

    data.append(node_info)

    # 处理子节点
    if hasattr(node, 'children'):
        node_info['has_children'] = len(node.children) > 0
        for child in node.children:
            child_path = node_info['path']
            data.extend(extract_simple_tree_data(child, depth + 1, child_path))

    return data


def create_single_version_tree(pf_tree, version, output_dir, max_depth=3):
    """创建单个版本的树形图"""
    print(f"   创建版本 {version} 的树形图...")

    # 提取树形数据
    tree_data = extract_simple_tree_data(pf_tree)
    df = pd.DataFrame(tree_data)

    # 创建图形
    fig, ax = plt.subplots(figsize=(15, 10))

    # 创建有向图
    G = nx.DiGraph()

    # 颜色映射：根据深度渐变
    cmap = plt.cm.Blues
    max_depth_in_tree = int(df['depth'].max())  # 转换为int

    # 添加节点和计算位置
    node_positions = {}
    node_colors = []
    node_sizes = []

    # 按深度分组
    depth_groups = df.groupby('depth')

    for idx, row in df.iterrows():
        if int(row['depth']) > max_depth:  # 确保是int
            continue

        node_name = row['path']
        depth = int(row['depth'])

        # 在深度层级中分配位置
        depth_df = df[df['depth'] == depth]
        node_index = list(depth_df.index).index(idx)

        # 计算位置
        x = depth * 3
        y = -node_index + len(depth_df) / 2

        node_positions[node_name] = (x, y)
        G.add_node(node_name)

        # 根据深度设置颜色
        if max_depth_in_tree > 0:
            color_value = depth / max_depth_in_tree
        else:
            color_value = 0

        node_colors.append(cmap(0.3 + color_value * 0.5))

        # 根据是否有子节点设置大小
        if row['has_children']:
            node_sizes.append(500)
        else:
            node_sizes.append(300)

    # 添加边（父子关系）
    for idx, row in df.iterrows():
        if int(row['depth']) > max_depth:
            continue

        node_path = row['path']
        parent_path = '.'.join(node_path.split('.')[:-1])

        if parent_path and parent_path in G.nodes:
            G.add_edge(parent_path, node_path)

    # 绘制树形图
    nx.draw(G, node_positions,
            node_color=node_colors,
            node_size=node_sizes,
            with_labels=True,
            font_size=8,
            font_weight='bold',
            edge_color='gray',
            width=1,
            alpha=0.8,
            arrows=True,
            arrowsize=10,
            ax=ax)

    # 添加标题和统计信息
    total_nodes = len(df)
    displayed_nodes = len([n for n in df['depth'] if int(n) <= max_depth])
    ax.set_title(f'版本 {version}\n总节点: {total_nodes}, 显示节点: {displayed_nodes}\n(深度≤{max_depth})',
                 fontsize=14, pad=20)

    # 添加深度图例
    legend_elements = []
    for depth in range(min(3, max_depth_in_tree + 1)):
        color = cmap(0.3 + (depth / max(max_depth_in_tree, 1)) * 0.5)
        legend_elements.append(Rectangle((0, 0), 1, 1, facecolor=color,
                                         label=f'深度 {depth}'))

    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))
    ax.axis('off')

    # 保存图片
    tree_png = os.path.join(output_dir, f'version_{version}_tree.png')
    plt.tight_layout()
    plt.savefig(tree_png, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"   版本 {version} 树形图已保存: {tree_png}")

    return tree_png, df


def create_aggregated_tree(pf_tree, lib_name, output_dir, max_depth=4):
    """创建聚合版本的树形图"""
    print(f"\n  创建聚合版本的树形图...")

    # 提取树形数据
    tree_data = extract_simple_tree_data(pf_tree)
    df = pd.DataFrame(tree_data)

    # 创建图形
    fig, ax = plt.subplots(figsize=(16, 12))

    # 创建有向图
    G = nx.DiGraph()

    # 颜色映射：根据深度渐变
    cmap = plt.cm.Greens
    max_depth_in_tree = int(df['depth'].max())

    # 添加节点和计算位置
    node_positions = {}
    node_colors = []
    node_sizes = []
    version_counts = {}

    # 为每个节点计算版本数量
    if hasattr(pf_tree, 'available_versions'):
        def collect_version_counts(node, path=""):
            node_name = getattr(node, 'name', 'Unknown')
            full_path = f"{path}.{node_name}" if path else node_name

            if hasattr(node, 'available_versions'):
                version_counts[full_path] = len(node.available_versions)

            if hasattr(node, 'children'):
                for child in node.children:
                    collect_version_counts(child, full_path)

        collect_version_counts(pf_tree)

    # 按深度分组
    depth_groups = df.groupby('depth')

    for idx, row in df.iterrows():
        if int(row['depth']) > max_depth:
            continue

        node_path = row['path']
        depth = int(row['depth'])

        # 在深度层级中分配位置
        depth_df = df[df['depth'] == depth]
        node_index = list(depth_df.index).index(idx)

        # 计算位置
        x = depth * 3
        y = -node_index + len(depth_df) / 2

        node_positions[node_path] = (x, y)
        G.add_node(node_path)

        # 根据深度设置颜色
        if max_depth_in_tree > 0:
            color_value = depth / max_depth_in_tree
        else:
            color_value = 0

        node_colors.append(cmap(0.3 + color_value * 0.5))

        # 根据版本数量设置大小
        version_count = version_counts.get(node_path, 1)
        node_sizes.append(300 + version_count * 30)

    # 添加边（父子关系）
    for idx, row in df.iterrows():
        if int(row['depth']) > max_depth:
            continue

        node_path = row['path']
        parent_path = '.'.join(node_path.split('.')[:-1])

        if parent_path and parent_path in G.nodes:
            G.add_edge(parent_path, node_path)

    # 绘制树形图
    nx.draw(G, node_positions,
            node_color=node_colors,
            node_size=node_sizes,
            with_labels=True,
            font_size=9,
            font_weight='bold',
            edge_color='#888888',
            width=1.2,
            alpha=0.8,
            arrows=True,
            arrowsize=12,
            ax=ax)

    # 添加标题和统计信息
    total_nodes = len(df)
    displayed_nodes = len([n for n in df['depth'] if int(n) <= max_depth])

    # 计算总版本数
    total_versions = 0
    if hasattr(pf_tree, 'available_versions'):
        total_versions = len(pf_tree.available_versions)

    title = f'{lib_name} - 聚合树形结构\n'
    title += f'总节点: {total_nodes}, 显示节点: {displayed_nodes}, 聚合版本数: {total_versions}\n'
    title += f'(深度≤{max_depth})'

    ax.set_title(title, fontsize=16, pad=20)

    # 添加图例
    legend_elements = [
        Rectangle((0, 0), 1, 1, facecolor=cmap(0.4), label='浅层节点'),
        Rectangle((0, 0), 1, 1, facecolor=cmap(0.7), label='中层节点'),
        Rectangle((0, 0), 1, 1, facecolor=cmap(0.9), label='深层节点')
    ]

    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))
    ax.axis('off')

    # 保存图片
    tree_png = os.path.join(output_dir, f'{lib_name}_aggregated_tree.png')
    plt.tight_layout()
    plt.savefig(tree_png, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"  聚合树形图已保存: {tree_png}")

    # 保存树结构数据为CSV
    csv_file = os.path.join(output_dir, f'{lib_name}_tree_structure.csv')
    df.to_csv(csv_file, index=False, encoding='utf-8')
    print(f"  树结构数据已保存: {csv_file}")

    return tree_png, df


def extract_all_nodes(node):
    """提取所有节点（BFS遍历）"""
    nodes = []
    queue = [node]

    while queue:
        current = queue.pop(0)
        nodes.append(current)

        if hasattr(current, 'children'):
            queue.extend(current.children)

    return nodes


def create_version_comparison_grid(version_trees, lib_name, output_dir):
    """创建版本树形图网格"""
    if not version_trees:
        return None

    print(f"\n  创建版本对比网格...")

    n_versions = len(version_trees)
    n_cols = min(3, n_versions)
    n_rows = (n_versions + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))

    if n_rows == 1 and n_cols == 1:
        axes = np.array([axes])
    elif n_rows == 1 or n_cols == 1:
        axes = axes.reshape(-1)

    axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    for idx, (version, tree_info) in enumerate(version_trees.items()):
        if idx >= len(axes_flat):
            break

        ax = axes_flat[idx]
        tree_data = tree_info['data']

        # 创建简单的节点统计图
        depth_counts = tree_data['depth'].value_counts().sort_index()

        # 只显示前4层深度
        if len(depth_counts) > 4:
            depth_counts = depth_counts[:4]

        colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(depth_counts)))

        bars = ax.bar(range(len(depth_counts)), depth_counts.values.astype(int), color=colors)
        ax.set_title(f'版本 {version}', fontsize=10)
        ax.set_xlabel('深度', fontsize=9)
        ax.set_ylabel('节点数', fontsize=9)
        ax.set_xticks(range(len(depth_counts)))
        ax.set_xticklabels([f'深度 {int(d)}' for d in depth_counts.index], fontsize=8)
        ax.tick_params(axis='both', which='major', labelsize=8)

        # 在柱子上显示数字
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height + 0.1,
                    f'{int(height)}', ha='center', va='bottom', fontsize=8)

    # 隐藏多余的子图
    for idx in range(len(version_trees), len(axes_flat)):
        axes_flat[idx].axis('off')

    plt.suptitle(f'{lib_name} - 各版本节点深度分布对比', fontsize=14, y=1.02)
    plt.tight_layout()

    grid_png = os.path.join(output_dir, f'{lib_name}_version_comparison.png')
    plt.savefig(grid_png, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"  版本对比网格已保存: {grid_png}")
    return grid_png


def create_evolution_timeline(version_trees, lib_name, output_dir):
    """创建演化时间线"""
    print(f"\n  创建演化时间线...")

    fig, ax = plt.subplots(figsize=(12, 6))

    # 收集数据
    versions = []
    total_nodes = []
    max_depths = []

    for version, tree_info in version_trees.items():
        versions.append(version)
        tree_data = tree_info['data']
        total_nodes.append(int(len(tree_data)))  # 转换为int
        max_depths.append(int(tree_data['depth'].max()))  # 转换为int

    # 绘制双y轴图
    ax1 = ax
    ax2 = ax1.twinx()

    # 节点数量线
    line1 = ax1.plot(versions, total_nodes, 'b-o', linewidth=2, markersize=8,
                     label='节点数量')
    ax1.set_xlabel('版本', fontsize=12)
    ax1.set_ylabel('节点数量', color='b', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='b')

    # 最大深度线
    line2 = ax2.plot(versions, max_depths, 'r-s', linewidth=2, markersize=8,
                     label='最大深度')
    ax2.set_ylabel('最大深度', color='r', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='r')

    # 组合图例
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    ax1.set_title(f'{lib_name} - API树演化时间线', fontsize=14, pad=20)
    ax1.grid(True, alpha=0.3)

    # 在每个点上方显示数值
    for i, (v, n, d) in enumerate(zip(versions, total_nodes, max_depths)):
        ax1.text(i, n + max(total_nodes) * 0.02, str(n), ha='center', va='bottom', fontsize=9)
        ax2.text(i, d + max(max_depths) * 0.02, str(d), ha='center', va='bottom', fontsize=9, color='r')

    plt.tight_layout()
    timeline_png = os.path.join(output_dir, f'{lib_name}_evolution_timeline.png')
    plt.savefig(timeline_png, dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"  演化时间线已保存: {timeline_png}")
    return timeline_png


def convert_to_serializable(obj):
    """将对象转换为可JSON序列化的格式"""
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict('records')
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    else:
        return obj


def visualize_all_trees(lib_name=None):
    """主函数：可视化所有树形结构"""
    print("=" * 60)
    print("PyMevol 树形结构可视化工具")
    print("=" * 60)

    # 检查目录
    if not os.path.exists('output_agg'):
        print("错误: output_agg目录不存在")
        return

    if not os.path.exists('output_profile'):
        print("⚠  warning: output_profile目录不存在，只能显示聚合树")

    # 查找可用的库
    lib_files = [f for f in os.listdir('output_agg') if f.endswith('.pickle')]

    if not lib_files:
        print("错误: 未找到聚合剖面文件")
        return

    print(f"  找到 {len(lib_files)} 个库:")
    for i, file in enumerate(lib_files, 1):
        print(f"  {i}. {file.replace('.pickle', '')}")

    # 选择库
    if lib_name is None:
        lib_file = lib_files[0]
        lib_name = lib_file.replace('.pickle', '')
        print(f"\n  自动选择第一个库: {lib_name}")
    else:
        lib_file = f"{lib_name}.pickle" if not lib_name.endswith('.pickle') else lib_name
        if lib_file not in lib_files:
            print(f"⚠ 未找到库 {lib_name}，使用第一个库")
            lib_file = lib_files[0]
            lib_name = lib_file.replace('.pickle', '')
        else:
            print(f"\n  分析指定库: {lib_name}")

    # 创建输出目录
    output_dir = f'tree_visualizations_{lib_name}'
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  输出目录: {output_dir}")

    try:
        # 1. 加载聚合树
        print(f"\n  加载聚合树...")
        agg_file = os.path.join('output_agg', lib_file)
        agg_tree = load_pickle_file(agg_file)
        print("  聚合树加载成功")

        # 2. 创建聚合树形图
        agg_tree_png, agg_df = create_aggregated_tree(agg_tree, lib_name, output_dir, max_depth=4)

        # 3. 加载各个版本的树
        version_trees = {}
        if os.path.exists('output_profile') and os.path.exists(os.path.join('output_profile', lib_name)):
            print(f"\n  加载各个版本的树...")
            version_dirs = os.listdir(os.path.join('output_profile', lib_name))

            if version_dirs:
                # 排序版本
                try:
                    from packaging import version as pkg_version
                    version_dirs.sort(key=lambda x: pkg_version.parse(x))
                except:
                    version_dirs.sort()

                # 限制处理的版本数量
                max_versions_to_process = 6
                selected_versions = version_dirs[-max_versions_to_process:]

                print(f"  发现 {len(version_dirs)} 个版本，处理最新的 {len(selected_versions)} 个版本")

                for version in selected_versions:
                    version_dir = os.path.join('output_profile', lib_name, version)
                    if os.path.exists(version_dir):
                        pickle_files = [f for f in os.listdir(version_dir) if f.endswith('.pickle')]
                        if pickle_files:
                            single_pickle = os.path.join(version_dir, pickle_files[0])
                            try:
                                single_tree = load_pickle_file(single_pickle)
                                print(f"    加载版本 {version}")

                                # 创建单个版本的树形图
                                tree_png, tree_df = create_single_version_tree(
                                    single_tree, version, output_dir, max_depth=3
                                )

                                version_trees[version] = {
                                    'tree': single_tree,
                                    'png': tree_png,
                                    'data': tree_df
                                }

                            except Exception as e:
                                print(f"    加载版本 {version} 失败: {e}")

        # 4. 创建版本对比
        if version_trees:
            # 创建版本对比网格
            grid_png = create_version_comparison_grid(version_trees, lib_name, output_dir)

            # 创建演化时间线
            timeline_png = create_evolution_timeline(version_trees, lib_name, output_dir)

            # 保存版本信息（修复JSON序列化问题）
            version_info = {
                'library': lib_name,
                'total_versions': len(version_trees),
                'versions': list(version_trees.keys()),
                'version_stats': {}
            }

            for version, info in version_trees.items():
                tree_df = info['data']
                version_info['version_stats'][version] = {
                    'total_nodes': int(len(tree_df)),  # 转换为int
                    'max_depth': int(tree_df['depth'].max()),  # 转换为int
                    'nodes_with_children': int(tree_df['has_children'].sum())  # 转换为int
                }

            # 转换为可序列化的格式
            version_info = convert_to_serializable(version_info)

            info_file = os.path.join(output_dir, f'{lib_name}_version_info.json')
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(version_info, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

            print(f"  版本信息已保存: {info_file}")

        # 5. 创建汇总报告
        create_summary_report(lib_name, agg_df, version_trees, output_dir)

        print(f"\n{'=' * 60}")
        print(f"  {lib_name} 树形结构可视化完成!")
        print(f"{'=' * 60}")
        print(f"  输出文件保存在: {output_dir}/")
        print(f"\n  主要输出文件:")
        print(f"  • {lib_name}_aggregated_tree.png - 聚合树形图")

        if version_trees:
            print(f"  • version_*.png - 各个版本的树形图 ({len(version_trees)}个)")
            print(f"  • {lib_name}_version_comparison.png - 版本对比网格")
            print(f"  • {lib_name}_evolution_timeline.png - 演化时间线")
            print(f"  • {lib_name}_tree_structure.csv - 树结构数据")
            print(f"  • {lib_name}_version_info.json - 版本信息")
            print(f"  • {lib_name}_summary_report.txt - 汇总报告")

        print(f"\n  聚合树统计:")
        print(f"  • 总节点数: {len(agg_df)}")
        print(f"  • 最大深度: {int(agg_df['depth'].max())}")
        print(f"  • 有子节点数: {int(agg_df['has_children'].sum())}")

        if version_trees:
            print(f"\n  处理的版本: {', '.join(list(version_trees.keys()))}")

        print(f"{'=' * 60}")

        return True

    except Exception as e:
        print(f"\n  处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_summary_report(lib_name, agg_df, version_trees, output_dir):
    """创建汇总报告"""
    print(f"\n  创建汇总报告...")

    report_lines = [
        "=" * 60,
        f"{lib_name} - 树形结构分析报告",
        "=" * 60,
        f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "1. 聚合树统计:",
        f"   • 总节点数: {len(agg_df)}",
        f"   • 最大深度: {int(agg_df['depth'].max())}",
        f"   • 有子节点数: {int(agg_df['has_children'].sum())}",
        f"   • 叶节点数: {int(len(agg_df[~agg_df['has_children']]))}",
        ""
    ]

    # 深度分布
    depth_dist = agg_df['depth'].value_counts().sort_index()
    report_lines.append("2. 深度分布:")
    for depth, count in depth_dist.items():
        percentage = (count / len(agg_df)) * 100
        report_lines.append(f"   • 深度 {int(depth)}: {int(count)} 节点 ({percentage:.1f}%)")

    report_lines.append("")

    if version_trees:
        report_lines.append("3. 版本树统计:")
        for version, info in version_trees.items():
            tree_df = info['data']
            report_lines.append(f"   版本 {version}:")
            report_lines.append(f"     • 节点数: {len(tree_df)}")
            report_lines.append(f"     • 最大深度: {int(tree_df['depth'].max())}")
            report_lines.append(f"     • 有子节点数: {int(tree_df['has_children'].sum())}")

        report_lines.append("")

        # 计算变化
        if len(version_trees) >= 2:
            versions = list(version_trees.keys())
            first_ver = versions[0]
            last_ver = versions[-1]

            first_df = version_trees[first_ver]['data']
            last_df = version_trees[last_ver]['data']

            node_growth = len(last_df) - len(first_df)
            depth_growth = int(last_df['depth'].max()) - int(first_df['depth'].max())

            report_lines.append("4. 版本间变化:")
            report_lines.append(f"   • 从 {first_ver} 到 {last_ver}")
            report_lines.append(f"   • 节点增长: {node_growth:+d}")
            report_lines.append(f"   • 深度变化: {depth_growth:+d}")

    report_lines.append("")
    report_lines.append("=" * 60)

    report_file = os.path.join(output_dir, f'{lib_name}_summary_report.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"  汇总报告已保存: {report_file}")
    return report_file


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        lib_name = sys.argv[1]
        visualize_all_trees(lib_name)
    else:
        # 可视化第一个库
        lib_files = [f for f in os.listdir('output_agg') if f.endswith('.pickle')] if os.path.exists(
            'output_agg') else []
        if lib_files:
            lib_name = lib_files[0].replace('.pickle', '')
            visualize_all_trees(lib_name)
        else:
            print("  未找到任何库数据")


if __name__ == "__main__":
    print("  提示: 请确保已安装依赖: pip install matplotlib seaborn pandas numpy networkx")
    main()