import os
import requests
import json
from urllib.parse import urljoin
from pathlib import Path


def download_package(package_name, max_versions=6):
    """下载指定Python包"""

    # 创建目录
    data_dir = Path("data/haowei/pypi_libs") / package_name
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在下载 {package_name}...")

    try:
        # 获取包信息
        url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        releases = data.get("releases", {})

        # 获取所有版本并排序
        versions = list(releases.keys())
        from packaging.version import parse as parse_version
        versions.sort(key=parse_version)

        print(f"找到 {len(versions)} 个版本")

        # 下载最新几个版本
        downloaded = 0
        for version in versions[-max_versions:]:
            if not releases[version]:
                continue

            # 创建版本目录
            version_dir = data_dir / version
            version_dir.mkdir(exist_ok=True)

            # 查找合适的文件
            for file_info in releases[version]:
                filename = file_info["filename"]
                file_url = file_info["url"]

                # 检查是否已存在
                file_path = version_dir / filename
                if file_path.exists():
                    print(f"  ✓ {version}: {filename} (已存在)")
                    downloaded += 1
                    break

                try:
                    print(f"  下载 {version}: {filename}")

                    # 下载文件
                    file_response = requests.get(file_url, stream=True, timeout=60)
                    file_response.raise_for_status()

                    with open(file_path, 'wb') as f:
                        for chunk in file_response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    print(f"    ✓ 下载完成")
                    downloaded += 1
                    break  # 每个版本只下载一个文件

                except Exception as e:
                    print(f"    ✗ 下载失败: {e}")
                    continue

        print(f"✓ {package_name}: 下载了 {downloaded}/{max_versions} 个版本")
        return downloaded > 0

    except Exception as e:
        print(f"✗ 下载 {package_name} 失败: {e}")
        return False


def main():
    # 读取要下载的包列表
    if os.path.exists("lib_names.txt"):
        with open("lib_names.txt", "r") as f:
            packages = [
                line.strip() for line in f
                if line.strip() and not line.startswith("#")
            ]
    else:
        # 默认包
        packages = ["requests", "numpy", "pandas"]
        print("使用默认包列表:", packages)

    print("=" * 50)
    print("开始下载包...")
    print("=" * 50)

    successful = []
    failed = []

    for package in packages:
        if download_package(package, max_versions=6):
            successful.append(package)
        else:
            failed.append(package)

    print("\n" + "=" * 50)
    print("下载完成！")
    print(f"成功: {len(successful)} 个包: {', '.join(successful)}")
    if failed:
        print(f"失败: {len(failed)} 个包: {', '.join(failed)}")

    # 显示目录结构
    if os.path.exists("pypi_libs"):
        print("\n目录结构:")
        for root, dirs, files in os.walk("pypi_libs"):
            level = root.replace("pypi_libs", "").count(os.sep)
            indent = " " * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files[:3]:  # 显示前3个文件
                print(f"{subindent}{file}")


if __name__ == "__main__":
    main()