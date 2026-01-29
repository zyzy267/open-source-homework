"""
GitHub Issue元数据收集脚本
具有错误处理、恢复能力和网络检测功能
"""

import requests
import json
import time
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('github_collector.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class GitHubIssueCollector:
    def __init__(self, token: Optional[str] = None):
        """
        初始化GitHub Issue收集器

        Args:
            token: GitHub个人访问令牌，如果为None则提示用户输入
        """
        self.token = token or self._get_token_from_user()
        self.base_url = "https://api.github.com"
        self.session = self._create_session()
        self.max_retries = 5
        self.retry_delay = 5  # 初始重试延迟秒数
        self.max_wait_time = 300  # 最大等待时间5分钟
        self.collected_data = []

    def _get_token_from_user(self) -> str:
        """从用户输入获取GitHub Token"""
        print("\n" + "=" * 60)
        print("GitHub Issue元数据收集器")
        print("=" * 60)

        token = input("请输入GitHub个人访问令牌: ").strip()
        if not token:
            logger.error("必须提供GitHub Token")
            sys.exit(1)

        # 验证token格式
        if not token.startswith(("ghp_", "github_pat_")):
            logger.warning("Token格式可能不正确，标准格式以'ghp_'或'github_pat_'开头")

        return token

    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitHub-Issue-Collector/1.0"
        })
        session.timeout = 30
        return session

    def _make_request_with_retry(self, url: str, params: Dict = None,
                                 method: str = "GET") -> Optional[requests.Response]:
        """
        带有重试机制的HTTP请求

        Args:
            url: 请求URL
            params: 查询参数
            method: HTTP方法

        Returns:
            响应对象，如果失败则返回None
        """
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"请求 {url} (尝试 {attempt + 1}/{self.max_retries})")

                if method.upper() == "GET":
                    response = self.session.get(url, params=params, timeout=30)
                elif method.upper() == "HEAD":
                    response = self.session.head(url, params=params, timeout=30)
                else:
                    response = self.session.get(url, params=params, timeout=30)

                # 处理成功响应
                if response.status_code in [200, 201, 202]:
                    return response

                # 处理特殊状态码
                elif response.status_code == 401:
                    logger.error("认证失败：无效的GitHub Token")
                    print(" 认证失败：请检查您的GitHub Token是否正确")
                    return None

                elif response.status_code == 403:
                    # 处理速率限制
                    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

                    if remaining == 0:
                        wait_time = max(reset_time - time.time(), 0) + 5
                        logger.warning(f"达到API速率限制，等待 {wait_time:.0f} 秒")
                        print(f" 达到API限制，等待 {wait_time:.0f} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"访问被拒绝: {response.status_code}")
                        print(f" 访问被拒绝 (HTTP {response.status_code})")
                        return None

                elif response.status_code == 404:
                    logger.error(f"资源不存在: {url}")
                    return None

                elif response.status_code in [500, 502, 503, 504]:
                    logger.warning(f"服务器错误: {response.status_code}")
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                    print(f" 服务器暂时不可用，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                else:
                    logger.error(f"HTTP错误 {response.status_code}: {response.text[:200]}")
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f" 请求超时，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                continue

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"连接错误: {e} (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f" 网络连接问题，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                continue

            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                continue

        # 所有重试都失败
        logger.error(f"所有 {self.max_retries} 次重试都失败")
        return None

    def check_repository_exists(self, repo_name: str) -> Tuple[bool, Dict]:
        """
        检查GitHub仓库是否存在

        Args:
            repo_name: 仓库名称，格式: owner/repo

        Returns:
            (是否存在, 仓库信息)
        """
        if '/' not in repo_name or repo_name.count('/') != 1:
            logger.error(f"仓库名称格式错误，应为 'owner/repo' 格式: {repo_name}")
            return False, {}

        url = f"{self.base_url}/repos/{repo_name}"
        logger.info(f"检查仓库是否存在: {repo_name}")

        response = self._make_request_with_retry(url, method="GET")

        if response and response.status_code == 200:
            repo_info = response.json()
            logger.info(f"仓库找到: {repo_info.get('full_name')}")
            logger.info(f"描述: {repo_info.get('description', '无描述')}")
            logger.info(f"星标数: {repo_info.get('stargazers_count')}")
            logger.info(f"最后更新: {repo_info.get('updated_at')}")
            return True, repo_info
        else:
            logger.error(f"仓库不存在或无法访问: {repo_name}")
            return False, {}

    def get_issues_for_repository(self, repo_name: str, state: str = "all",
                                  per_page: int = 100, max_pages: int = 100) -> List[Dict]:
        """
        获取指定仓库的所有Issue

        Args:
            repo_name: 仓库名称
            state: Issue状态 (all, open, closed)
            per_page: 每页数量
            max_pages: 最大页数限制

        Returns:
            Issue列表
        """
        issues = []
        page = 1
        has_more_pages = True

        # 检查点文件路径
        checkpoint_file = f"checkpoint_{repo_name.replace('/', '_')}.json"

        # 尝试从检查点恢复
        checkpoint = self._load_checkpoint(checkpoint_file)
        if checkpoint:
            page = checkpoint.get('page', 1)
            issues = checkpoint.get('issues', [])
            logger.info(f"从检查点恢复: 第 {page} 页，已收集 {len(issues)} 个Issue")

        # 进度跟踪
        start_time = time.time()
        last_save_time = time.time()
        save_interval = 60  # 每60秒保存一次

        try:
            while has_more_pages and page <= max_pages:
                logger.info(f"获取 {repo_name} 的Issue数据，第 {page} 页...")

                url = f"{self.base_url}/repos/{repo_name}/issues"
                params = {
                    "state": state,
                    "per_page": per_page,
                    "page": page,
                    "direction": "asc",  # 按创建时间升序
                    "filter": "all"  # 包括所有Issue和PR
                }

                response = self._make_request_with_retry(url, params)

                if not response:
                    logger.error(f"第 {page} 页获取失败")
                    if page > 1:
                        logger.info("保存已收集的数据...")
                        self._save_checkpoint(checkpoint_file, page, issues)
                    break

                batch_issues = response.json()

                if not batch_issues:
                    logger.info(f"第 {page} 页无数据，完成收集")
                    has_more_pages = False
                    break

                # 解析Issue数据
                parsed_issues = []
                seen_issue_numbers = {issue.get('number') for issue in issues}

                for issue in batch_issues:
                    issue_number = issue.get("number")

                    # 跳过已收集的Issue
                    if issue_number in seen_issue_numbers:
                        continue

                    issue_data = self._parse_issue_data(issue)
                    parsed_issues.append(issue_data)
                    seen_issue_numbers.add(issue_number)

                issues.extend(parsed_issues)
                logger.info(f"第 {page} 页: 收集到 {len(parsed_issues)} 个新Issue，总计 {len(issues)} 个")

                # 检查是否有下一页
                if len(batch_issues) < per_page:
                    logger.info(f"第 {page} 页数据不足 {per_page} 条，可能是最后一页")
                    has_more_pages = False
                else:
                    page += 1

                # 定期保存检查点
                current_time = time.time()
                if current_time - last_save_time > save_interval or not has_more_pages:
                    self._save_checkpoint(checkpoint_file, page, issues)
                    last_save_time = current_time

                # 避免请求过快
                time.sleep(0.5)

            # 收集完成
            elapsed_time = time.time() - start_time
            logger.info(f"数据收集完成！耗时 {elapsed_time:.1f} 秒，共收集 {len(issues)} 个Issue")

            # 清理检查点文件
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
                logger.info(f"检查点文件已清理: {checkpoint_file}")

            return issues

        except Exception as e:
            logger.error(f"收集过程中发生异常: {e}")
            logger.info("保存已收集的数据到检查点...")
            self._save_checkpoint(checkpoint_file, page, issues)
            raise

    def _parse_issue_data(self, issue: Dict) -> Dict[str, Any]:
        """解析Issue数据"""
        # 安全获取labels
        labels = []
        if issue.get("labels"):
            labels = [
                label.get("name", "")
                for label in issue["labels"]
                if label and isinstance(label, dict) and label.get("name")
            ]

        # 安全获取user信息
        user_login = None
        if issue.get("user") and isinstance(issue["user"], dict):
            user_login = issue["user"].get("login")

        return {
            "id": issue.get("id"),
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "closed_at": issue.get("closed_at"),
            "state": issue.get("state", "").lower(),
            "comments_count": issue.get("comments", 0),
            "labels": labels,
            "user_login": user_login,
            "is_pull_request": "pull_request" in issue,
            "body_length": len(issue.get("body") or ""),
            "html_url": issue.get("html_url", ""),
            "locked": issue.get("locked", False),
            "assignee_count": len(issue.get("assignees", []))
        }

    def _save_checkpoint(self, checkpoint_file: str, page: int, issues: List[Dict]):
        """保存检查点"""
        try:
            checkpoint_data = {
                "timestamp": datetime.now().isoformat(),
                "page": page,
                "total_issues": len(issues),
                "issues": issues
            }

            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2, default=str)

            logger.debug(f"检查点保存到: {checkpoint_file} (第 {page} 页)")
        except Exception as e:
            logger.error(f"保存检查点失败: {e}")

    def _load_checkpoint(self, checkpoint_file: str) -> Optional[Dict]:
        """加载检查点"""
        if not os.path.exists(checkpoint_file):
            return None

        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"加载检查点: {checkpoint_file}")
            logger.info(f"  时间: {data.get('timestamp')}")
            logger.info(f"  页数: {data.get('page')}")
            logger.info(f"  Issue数: {data.get('total_issues')}")
            return data
        except Exception as e:
            logger.error(f"加载检查点失败: {e}")
            return None

    def save_issues_to_file(self, issues: List[Dict], repo_name: str,
                            output_dir: str = "data"):
        """
        保存Issue数据到文件

        Args:
            issues: Issue列表
            repo_name: 仓库名称
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        # 创建安全的文件名
        safe_repo_name = repo_name.replace('/', '_').replace('\\', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON文件
        json_file = os.path.join(output_dir, f"{safe_repo_name}_issues_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"JSON数据已保存: {json_file}")

        # CSV文件
        if issues:
            csv_file = os.path.join(output_dir, f"{safe_repo_name}_issues_{timestamp}.csv")
            import csv

            fieldnames = issues[0].keys()
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for issue in issues:
                    row = issue.copy()
                    if isinstance(row["labels"], list):
                        row["labels"] = ";".join(row["labels"])
                    writer.writerow(row)
            logger.info(f"CSV数据已保存: {csv_file}")

        return json_file

    def print_statistics(self, issues: List[Dict], repo_name: str):
        """打印统计信息"""
        if not issues:
            print("没有收集到数据")
            return

        print("\n" + "=" * 60)
        print(f" {repo_name} 项目Issue统计")
        print("=" * 60)

        total = len(issues)
        open_issues = len([i for i in issues if i["state"] == "open"])
        closed_issues = len([i for i in issues if i["state"] == "closed"])
        pr_count = len([i for i in issues if i["is_pull_request"]])

        print(f"总计 Issue/PR 数量: {total:,}")
        print(f"Open Issues: {open_issues:,} ({open_issues / total * 100:.1f}%)")
        print(f"Closed Issues: {closed_issues:,} ({closed_issues / total * 100:.1f}%)")
        print(f"Pull Requests: {pr_count:,} ({pr_count / total * 100:.1f}%)")

        # 时间范围
        dates = [i["created_at"] for i in issues if i["created_at"]]
        if dates:
            dates.sort()
            print(f"时间范围: {dates[0]} 到 {dates[-1]}")

        # 标签统计
        all_labels = []
        for issue in issues:
            if issue.get("labels"):
                all_labels.extend(issue["labels"])

        if all_labels:
            from collections import Counter
            label_counts = Counter(all_labels)
            print(f"标签总数: {len(all_labels):,} (去重: {len(label_counts):,})")

        print("=" * 60)


def check_network_connectivity() -> bool:
    """
    检查网络连接性

    Returns:
        网络是否可用
    """
    test_urls = [
        "https://api.github.com",
        "https://www.google.com",
        "https://www.baidu.com"
    ]

    for url in test_urls:
        try:
            response = requests.head(url, timeout=10)
            if response.status_code < 500:
                logger.info(f"网络连接正常: {url}")
                return True
        except Exception as e:
            logger.debug(f"网络检查失败 {url}: {e}")
            continue

    return False


def handle_critical_error(collector: GitHubIssueCollector, error: Exception):
    """
    处理严重错误

    Args:
        collector: 收集器实例
        error: 异常对象
    """
    print("\n" + "=" * 60)
    print(" 发生不可恢复错误")
    print("=" * 60)
    print(f"错误类型: {type(error).__name__}")
    print(f"错误信息: {str(error)[:200]}")

    # 检查网络连接
    print("\n正在检测您的网络环境...")
    for i in range(3):  # 尝试3次网络检测
        print(f"网络检测尝试 {i + 1}/3...")
        if check_network_connectivity():
            print("网络连接正常")
            return

        wait_time = 60  # 每次等待60秒
        print(f" 网络检测失败，等待 {wait_time} 秒后重试...")
        time.sleep(wait_time)

    print("网络检测失败，请检查您的网络连接")
    print("程序将在长时间等待后退出...")
    print("=" * 60)

    # 长时间等待
    for remaining in range(300, 0, -60):  # 5分钟倒计时
        if remaining > 60:
            print(f"⏳ 等待 {remaining // 60} 分钟 {remaining % 60} 秒后退出...")
        else:
            print(f"⏳ 等待 {remaining} 秒后退出...")
        time.sleep(60)

    print("程序退出")
    sys.exit(1)


def get_repository_name() -> str:
    """获取用户输入的仓库名称"""
    while True:
        print("\n" + "=" * 60)
        print("📦 GitHub仓库Issue收集器")
        print("=" * 60)
        print("支持的仓库格式:")
        print("  - owner/repository  (例如: encode/httpx)")
        print("  - psf/requests")
        print("  - facebook/react")
        print("=" * 60)

        repo_name = input("请输入GitHub仓库名称 (owner/repo): ").strip()

        if not repo_name:
            print("仓库名称不能为空")
            continue

        if '/' not in repo_name or repo_name.count('/') != 1:
            print("格式错误！请使用 'owner/repository' 格式")
            continue

        return repo_name


def main():
    """主函数"""
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='GitHub Issue元数据收集器')
        parser.add_argument('--token', help='GitHub访问令牌')
        parser.add_argument('--repo', help='GitHub仓库名称 (owner/repo)')
        parser.add_argument('--state', default='all', choices=['all', 'open', 'closed'],
                            help='Issue状态')
        parser.add_argument('--max-pages', type=int, default=100,
                            help='最大页数限制')
        parser.add_argument('--output-dir', default='data',
                            help='输出目录')

        args = parser.parse_args()

        # 创建收集器
        collector = GitHubIssueCollector(token=args.token)

        # 获取仓库名称
        repo_name = args.repo or get_repository_name()

        # 检查仓库是否存在
        exists, repo_info = collector.check_repository_exists(repo_name)
        if not exists:
            print(f"\n 仓库不存在或无法访问: {repo_name}")
            print("请检查:")
            print("  1. 仓库名称是否正确")
            print("  2. 仓库是否为公开仓库")
            print("  3. 您的GitHub Token是否有访问权限")
            return

        print(f"\n 找到仓库: {repo_name}")
        print(f"  描述: {repo_info.get('description', '无描述')}")
        print(f"  星标数: {repo_info.get('stargazers_count'):,}")
        print(f"  最后更新: {repo_info.get('updated_at')}")

        # 确认是否继续
        confirm = input("\n是否开始收集Issue数据？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes', '是']:
            print("操作取消")
            return

        # 开始收集
        print(f"\n 开始收集 {repo_name} 的Issue数据...")
        print("注意: 这可能需要几分钟到几小时，取决于仓库大小")
        print("=" * 60)

        try:
            issues = collector.get_issues_for_repository(
                repo_name=repo_name,
                state=args.state,
                per_page=100,
                max_pages=args.max_pages
            )

            if issues:
                # 保存数据
                json_file = collector.save_issues_to_file(
                    issues=issues,
                    repo_name=repo_name,
                    output_dir=args.output_dir
                )

                # 打印统计
                collector.print_statistics(issues, repo_name)

                print(f"\n 数据收集完成！")
                print(f" 数据文件: {json_file}")
                print(f" Issue数量: {len(issues):,}")
                print("=" * 60)
            else:
                print("\n 没有收集到Issue数据")
                print("可能的原因:")
                print("  1. 仓库没有Issue")
                print("  2. API访问受限")
                print("  3. 网络问题")

        except Exception as e:
            logger.error(f"收集过程中发生严重错误: {e}", exc_info=True)
            handle_critical_error(collector, e)

    except KeyboardInterrupt:
        print("\n\n 用户中断操作")
        print("已保存的数据可以在data目录找到")

    except Exception as e:
        print(f"\n 程序发生未预期错误: {e}")
        logger.error(f"主程序错误: {e}", exc_info=True)
        print("请检查日志文件: github_collector.log")


if __name__ == "__main__":
    main()