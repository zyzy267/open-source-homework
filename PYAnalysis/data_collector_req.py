import requests
import json
import time
from datetime import datetime
import argparse
import logging
from typing import Dict, List, Any, Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubIssueCollector:
    def __init__(self, token: str, owner: str = "psf", repo: str = "requests"):
        """
        初始化GitHub Issue收集器

        Args:
            token: GitHub个人访问令牌
            owner: 仓库所有者
            repo: 仓库名称
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"

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

        while True:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/issues"
            params = {
                "state": state,
                "per_page": per_page,
                "page": page,
                "direction": "asc"  # 按创建时间升序排列
            }

            logger.info(f"获取第 {page} 页数据...")

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                batch_issues = response.json()

                if not batch_issues:
                    logger.info("已获取所有Issue数据")
                    break

                for issue in batch_issues:
                    issue_data = self._parse_issue_data(issue)
                    issues.append(issue_data)

                logger.info(f"已收集 {len(issues)} 个Issue")

                # 检查是否有下一页
                if len(batch_issues) < per_page:
                    break

                page += 1

                # 遵守GitHub API速率限制
                remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

                if remaining <= 10:
                    wait_time = max(reset_time - time.time(), 0) + 10
                    logger.warning(f"接近API限制，等待 {wait_time:.0f} 秒")
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
                break

        return issues

    def _parse_issue_data(self, issue: Dict) -> Dict[str, Any]:
        """解析Issue数据，提取所需字段"""
        # 安全地获取labels
        labels = []
        if issue.get("labels"):
            labels = [label.get("name", "") for label in issue["labels"] if label.get("name")]

        # 安全地获取user_login
        user_login = None
        if issue.get("user") and issue["user"].get("login"):
            user_login = issue["user"]["login"]

        # 安全地获取body_length
        body = issue.get("body")
        body_length = len(body) if body is not None else 0

        return {
            "id": issue.get("id"),
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "closed_at": issue.get("closed_at"),
            "state": issue.get("state"),
            "comments_count": issue.get("comments", 0),
            "labels": labels,
            "user_login": user_login,
            "is_pull_request": "pull_request" in issue,
            "body_length": body_length,  # 修复这里
            "html_url": issue.get("html_url", "")
        }

    def save_to_file(self, issues: List[Dict], filename: str = "issues_data.json"):
        """保存数据到JSON文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已保存到 {filename}，共 {len(issues)} 条记录")

    def save_to_csv(self, issues: List[Dict], filename: str = "issues_data.csv"):
        """保存数据到CSV文件"""
        import csv

        if not issues:
            logger.warning("没有数据可保存")
            return

        # 准备CSV字段
        fieldnames = [
            "id", "number", "title", "created_at", "updated_at",
            "closed_at", "state", "comments_count", "labels",
            "user_login", "is_pull_request", "body_length", "html_url"
        ]

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for issue in issues:
                row = issue.copy()
                # 将labels列表转换为逗号分隔的字符串
                if isinstance(row["labels"], list):
                    row["labels"] = ",".join(row["labels"])
                writer.writerow(row)

        logger.info(f"数据已保存到 {filename}")


def main():
    parser = argparse.ArgumentParser(description='收集GitHub Issue数据')
    parser.add_argument('--token', required=True, help='GitHub访问令牌')
    parser.add_argument('--owner', default='psf', help='仓库所有者')
    parser.add_argument('--repo', default='requests', help='仓库名称')
    parser.add_argument('--state', default='all', choices=['all', 'open', 'closed'],
                        help='Issue状态')
    parser.add_argument('--output-json', default='issues_data.json',
                        help='输出JSON文件名')
    parser.add_argument('--output-csv', default='issues_data.csv',
                        help='输出CSV文件名')

    args = parser.parse_args()

    # 创建收集器
    collector = GitHubIssueCollector(args.token, args.owner, args.repo)

    # 收集数据
    logger.info(f"开始收集 {args.owner}/{args.repo} 的Issue数据...")
    issues = collector.get_all_issues(state=args.state)

    if issues:
        # 保存数据
        collector.save_to_file(issues, args.output_json)
        collector.save_to_csv(issues, args.output_csv)

        # 打印统计信息
        open_issues = len([i for i in issues if i["state"] == "open"])
        closed_issues = len([i for i in issues if i["state"] == "closed"])
        pr_count = len([i for i in issues if i["is_pull_request"]])

        logger.info(f"数据统计:")
        logger.info(f"  - 总计: {len(issues)} 个Issue/PR")
        logger.info(f"  - Open: {open_issues}")
        logger.info(f"  - Closed: {closed_issues}")
        logger.info(f"  - Pull Requests: {pr_count}")
        logger.info(f"  - 时间范围: {issues[0]['created_at']} 到 {issues[-1]['created_at']}")
    else:
        logger.error("未能获取到数据")


if __name__ == "__main__":
    main()