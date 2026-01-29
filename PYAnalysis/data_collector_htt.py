"""
GitHub httpx项目Issue元数据收集脚本
"""
import json
import time
import re
from datetime import datetime
import argparse
import logging
import csv
import os
from typing import Dict, List, Any, Optional, Set

import requests

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HTTPXIssueCollector:
    def __init__(self, token: str, owner: str = "encode", repo: str = "httpx"):
        """
        初始化httpx Issue收集器

        Args:
            token: GitHub个人访问令牌
            owner: 仓库所有者
            repo: 仓库名称
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_all_issues(self, state: str = "all", per_page: int = 100) -> List[Dict]:
        """
        获取所有Issue（包括Pull Request）

        Args:
            state: Issue状态 (all, open, closed)
            per_page: 每页数量

        Returns:
            Issue列表
        """
        issues = []
        page = 1

        # 记录已获取的issue编号，避免重复
        seen_issue_numbers: Set[int] = set()

        # 记录开始时间
        start_time = time.time()
        total_requests = 0

        logger.info(f"开始收集 {self.owner}/{self.repo} 的Issue数据...")

        while True:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues"
            params = {
                "state": state,
                "per_page": per_page,
                "page": page,
                "direction": "asc",  # 按创建时间升序排列
                "filter": "all"  # 获取所有Issue，包括Pull Request
            }

            logger.info(f"获取第 {page} 页数据...")
            total_requests += 1

            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                batch_issues = response.json()

                if not batch_issues:
                    logger.info("已获取所有Issue数据")
                    break

                for issue in batch_issues:
                    # 检查是否已处理过这个issue
                    issue_number = issue.get("number")
                    if issue_number is None or issue_number in seen_issue_numbers:
                        continue
                    seen_issue_numbers.add(issue_number)

                    # 解析issue数据
                    issue_data = self._parse_issue_data(issue)
                    issues.append(issue_data)

                    # 每收集10个issue显示一次进度
                    if len(issues) % 10 == 0:
                        logger.info(f"已收集 {len(issues)} 个Issue/PR")

                # 检查是否有下一页
                if len(batch_issues) < per_page:
                    break

                page += 1

                # 遵守GitHub API速率限制
                remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

                if remaining <= 5:
                    wait_time = max(reset_time - time.time(), 0) + 5
                    logger.warning(f"接近API限制，剩余 {remaining} 次请求，等待 {wait_time:.0f} 秒")
                    time.sleep(wait_time)
                else:
                    time.sleep(0.5)  # 避免过于频繁请求

            except requests.exceptions.RequestException as e:
                logger.error(f"获取数据失败: {e}")
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(reset_time - time.time(), 0) + 10
                    logger.warning(f"达到API限制，等待 {wait_time:.0f} 秒")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 422:
                    logger.error("API返回422错误，可能达到了分页限制")
                    break
                else:
                    logger.error(f"HTTP错误: {response.status_code}")
                    break
            except Exception as e:
                logger.error(f"处理数据时出错: {e}")
                break

        # 统计信息
        elapsed_time = time.time() - start_time
        logger.info(f"数据收集完成！耗时 {elapsed_time:.1f} 秒")
        logger.info(f"总请求次数: {total_requests}")
        logger.info(f"总收集Issue/PR数: {len(issues)}")

        return issues

    def _parse_issue_data(self, issue: Dict) -> Dict[str, Any]:
        """解析Issue数据，提取所需字段"""
        # 安全地获取labels
        labels = []
        if issue.get("labels"):
            labels = [
                label.get("name", "")
                for label in issue["labels"]
                if label and isinstance(label, dict) and label.get("name")
            ]

        # 安全地获取user_login
        user_login = None
        if issue.get("user") and isinstance(issue["user"], dict):
            user_login = issue["user"].get("login")

        # 判断是否是Pull Request
        is_pull_request = "pull_request" in issue

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
            "is_pull_request": is_pull_request,
            "body_length": len(issue.get("body") or ""),
            "html_url": issue.get("html_url", ""),
            "locked": issue.get("locked", False),
            "assignee_count": len(issue.get("assignees", [])),
            "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None
        }

    def save_to_json(self, issues: List[Dict], filename: str = "issues_data.json"):
        """保存数据到JSON文件"""
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"数据已保存到 {filename}，共 {len(issues)} 条记录")

    def save_to_csv(self, issues: List[Dict], filename: str = "httpx_issues.csv"):
        """保存数据到CSV文件"""
        if not issues:
            logger.warning("没有数据可保存")
            return

        # 准备CSV字段
        fieldnames = [
            "id", "number", "title", "created_at", "updated_at",
            "closed_at", "state", "comments_count", "labels",
            "user_login", "is_pull_request", "body_length",
            "html_url", "locked", "assignee_count", "milestone"
        ]

        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for issue in issues:
                row = issue.copy()
                # 将labels列表转换为分号分隔的字符串
                if isinstance(row["labels"], list):
                    row["labels"] = ";".join([str(label) for label in row["labels"] if label])
                writer.writerow(row)

        logger.info(f"数据已保存到 {filename}")


def main():
    parser = argparse.ArgumentParser(description='收集GitHub httpx项目Issue数据')
    parser.add_argument('--token', type=str, required=True, help='GitHub访问令牌')
    parser.add_argument('--owner', type=str, default='encode', help='仓库所有者')
    parser.add_argument('--repo', type=str, default='httpx', help='仓库名称')
    parser.add_argument('--state', type=str, default='all',
                        choices=['all', 'open', 'closed'], help='Issue状态')
    parser.add_argument('--output-json', type=str, default='data/issues_data.json',
                        help='输出JSON文件名')
    parser.add_argument('--output-csv', type=str, default='data/httpx_issues.csv',
                        help='输出CSV文件名')

    args = parser.parse_args()

    # 创建收集器
    collector = HTTPXIssueCollector(args.token, args.owner, args.repo)

    # 收集数据
    issues = collector.get_all_issues(state=args.state)

    if issues:
        # 保存数据
        collector.save_to_json(issues, args.output_json)
        collector.save_to_csv(issues, args.output_csv)

        # 统计信息
        open_issues = len([i for i in issues if i["state"] == "open"])
        closed_issues = len([i for i in issues if i["state"] == "closed"])
        pr_count = len([i for i in issues if i["is_pull_request"]])

        print("\n" + "=" * 60)
        print("数据收集完成！")
        print("=" * 60)
        print(f"总计收集: {len(issues)} 个Issue/PR")
        print(f"  - Open状态: {open_issues} 个 ({open_issues / len(issues) * 100:.1f}%)")
        print(f"  - Closed状态: {closed_issues} 个 ({closed_issues / len(issues) * 100:.1f}%)")
        print(f"  - Pull Requests: {pr_count} 个 ({pr_count / len(issues) * 100:.1f}%)")

        if issues:
            first_date = issues[0].get('created_at', '未知')
            last_date = issues[-1].get('created_at', '未知')
            print(f"  - 时间范围: {first_date} 到 {last_date}")

        # 输出文件信息
        print(f"\n数据文件:")
        print(f"  - JSON格式: {args.output_json}")
        print(f"  - CSV格式: {args.output_csv}")
        print("=" * 60)
    else:
        logger.error("未能获取到数据")


if __name__ == "__main__":
    main()