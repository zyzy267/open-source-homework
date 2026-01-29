import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import argparse
import logging
from collections import Counter
import warnings

warnings.filterwarnings('ignore')

# Set Chinese font display and graphic style
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
sns.set_palette("husl")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IssueAnalyzer:
    def __init__(self, data_file: str):
        """
        Initialize Issue analyzer

        Args:
            data_file: Issue data file path
        """
        self.data_file = data_file
        self.df = self.load_data()

    def load_data(self) -> pd.DataFrame:
        """Load data"""
        logger.info(f"Loading data file: {self.data_file}")

        if self.data_file.endswith('.json'):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        else:  # CSV file
            df = pd.read_csv(self.data_file)
            # Convert labels string back to list
            if 'labels' in df.columns:
                df['labels'] = df['labels'].apply(lambda x: x.split(',') if isinstance(x, str) else [])

        # Convert date columns
        date_columns = ['created_at', 'updated_at', 'closed_at']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])

        logger.info(f"Loading completed, total {len(df)} records")
        return df

    def basic_statistics(self):
        """Basic statistical analysis"""
        print("=" * 60)
        print("Basic Statistical Analysis")
        print("=" * 60)

        # Overall statistics
        total_issues = len(self.df)
        open_issues = len(self.df[self.df['state'] == 'open'])
        closed_issues = len(self.df[self.df['state'] == 'closed'])
        pr_count = self.df['is_pull_request'].sum() if 'is_pull_request' in self.df.columns else 0

        print(f"Total Issue/PR count: {total_issues}")
        print(f"Open Issue count: {open_issues} ({open_issues / total_issues * 100:.1f}%)")
        print(f"Closed Issue count: {closed_issues} ({closed_issues / total_issues * 100:.1f}%)")
        print(f"Pull Request count: {pr_count} ({pr_count / total_issues * 100:.1f}%)")

        # Time range
        if 'created_at' in self.df.columns:
            min_date = self.df['created_at'].min()
            max_date = self.df['created_at'].max()
            print(f"Time range: {min_date.date()} to {max_date.date()}")
            print(f"Duration: {(max_date - min_date).days} days")

        # Comments statistics
        if 'comments_count' in self.df.columns:
            print(f"\nComments statistics:")
            print(f"  Average comments: {self.df['comments_count'].mean():.1f}")
            print(f"  Median comments: {self.df['comments_count'].median():.1f}")
            print(f"  Maximum comments: {self.df['comments_count'].max()}")
            print(f"  Zero comment Issues: {len(self.df[self.df['comments_count'] == 0])}")

        return {
            'total_issues': total_issues,
            'open_issues': open_issues,
            'closed_issues': closed_issues,
            'pr_count': pr_count
        }

    def temporal_analysis(self):
        """Time series analysis"""
        print("\n" + "=" * 60)
        print("Time Series Analysis")
        print("=" * 60)

        if 'created_at' not in self.df.columns:
            print("Missing creation time data")
            return

        # Count creation by year/month
        self.df['created_year'] = self.df['created_at'].dt.year
        self.df['created_month'] = self.df['created_at'].dt.to_period('M')
        self.df['created_year_month'] = self.df['created_at'].dt.strftime('%Y-%m')

        # Count by month
        monthly_counts = self.df.groupby('created_year_month').size()

        # Count by year
        yearly_counts = self.df.groupby('created_year').size()

        print("Annual Issue creation count:")
        for year, count in yearly_counts.items():
            print(f"  {year}: {count}")

        # Calculate close time (if closed_at exists)
        if 'closed_at' in self.df.columns and 'created_at' in self.df.columns:
            closed_df = self.df[self.df['state'] == 'closed'].copy()
            if len(closed_df) > 0:
                closed_df['resolve_time_days'] = (closed_df['closed_at'] - closed_df[
                    'created_at']).dt.total_seconds() / (24 * 3600)
                print(f"\nIssue resolution time analysis:")
                print(f"  Average resolution time: {closed_df['resolve_time_days'].mean():.1f} days")
                print(f"  Median resolution time: {closed_df['resolve_time_days'].median():.1f} days")
                print(f"  Shortest resolution time: {closed_df['resolve_time_days'].min():.1f} days")
                print(f"  Longest resolution time: {closed_df['resolve_time_days'].max():.1f} days")

        return monthly_counts, yearly_counts

    def label_analysis(self, top_n: int = 20):
        """Label analysis"""
        print("\n" + "=" * 60)
        print("Label Analysis")
        print("=" * 60)

        if 'labels' not in self.df.columns:
            print("No label data")
            return

        # Count all labels
        all_labels = []
        for labels in self.df['labels']:
            if isinstance(labels, list):
                all_labels.extend(labels)

        label_counts = Counter(all_labels)

        print(f"Total {len(label_counts)} different labels")
        print(f"\nTop {top_n} most used labels:")

        for label, count in label_counts.most_common(top_n):
            print(f"  {label}: {count} times ({count / len(self.df) * 100:.1f}%)")

        # Count issues without labels
        no_label_count = self.df['labels'].apply(lambda x: len(x) if isinstance(x, list) else 0) == 0
        print(f"\nIssues without labels: {no_label_count.sum()} ({no_label_count.sum() / len(self.df) * 100:.1f}%)")

        return label_counts

    def user_analysis(self, top_n: int = 10):
        """User contribution analysis"""
        print("\n" + "=" * 60)
        print("User Contribution Analysis")
        print("=" * 60)

        if 'user_login' not in self.df.columns:
            print("No user data")
            return

        # Count issues created by users
        user_issue_counts = self.df['user_login'].value_counts()

        print(f"Total {len(user_issue_counts)} users created issues")
        print(f"\nTop {top_n} users who created the most issues:")

        for i, (user, count) in enumerate(user_issue_counts.head(top_n).items(), 1):
            print(f"  {i:2d}. {user}: {count} ({count / len(self.df) * 100:.1f}%)")

        return user_issue_counts

    def comments_analysis(self):
        """Comments analysis"""
        print("\n" + "=" * 60)
        print("Comments Analysis")
        print("=" * 60)

        if 'comments_count' not in self.df.columns:
            print("No comment data")
            return

        # Comments count distribution
        print("Comments count distribution:")
        print(
            f"  Zero comments: {len(self.df[self.df['comments_count'] == 0])} ({len(self.df[self.df['comments_count'] == 0]) / len(self.df) * 100:.1f}%)")
        print(f"  1-5 comments: {len(self.df[(self.df['comments_count'] > 0) & (self.df['comments_count'] <= 5)])}")
        print(f"  6-10 comments: {len(self.df[(self.df['comments_count'] > 5) & (self.df['comments_count'] <= 10)])}")
        print(f"  10+ comments: {len(self.df[self.df['comments_count'] > 10])}")

        # Relationship between comments count and state
        if 'state' in self.df.columns:
            print("\nAverage comments by issue state:")
            state_comments = self.df.groupby('state')['comments_count'].agg(['mean', 'median', 'count'])
            for state, row in state_comments.iterrows():
                print(
                    f"  {state}: average {row['mean']:.1f} comments, median {row['median']:.1f} comments, total {int(row['count'])}")

    def create_visualizations(self, output_dir: str = "plots"):
        """Create visualization charts"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        # 1. Issue creation time trend
        if 'created_year_month' in self.df.columns:
            plt.figure(figsize=(14, 6))

            # Count by year-month
            monthly_counts = self.df['created_year_month'].value_counts().sort_index()

            # Draw line chart
            plt.subplot(1, 2, 1)
            monthly_counts.plot(kind='line', marker='o')
            plt.title('Issue Creation Trend (Monthly)')
            plt.xlabel('Year-Month')
            plt.ylabel('Issue Count')
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)

            # Draw bar chart
            plt.subplot(1, 2, 2)
            yearly_counts = self.df['created_year'].value_counts().sort_index()
            yearly_counts.plot(kind='bar')
            plt.title('Issue Creation Trend (Yearly)')
            plt.xlabel('Year')
            plt.ylabel('Issue Count')

            plt.tight_layout()
            plt.savefig(f'{output_dir}/issue_creation_trend.png', dpi=300, bbox_inches='tight')
            plt.close()

        # 2. Issue state distribution
        if 'state' in self.df.columns:
            plt.figure(figsize=(10, 6))

            # Pie chart
            state_counts = self.df['state'].value_counts()
            plt.pie(state_counts.values, labels=state_counts.index, autopct='%1.1f%%')
            plt.title('Issue State Distribution')

            plt.savefig(f'{output_dir}/issue_state_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()

        # 3. Label wordcloud (top 20)
        if 'labels' in self.df.columns:
            from wordcloud import WordCloud

            all_labels = []
            for labels in self.df['labels']:
                if isinstance(labels, list):
                    all_labels.extend(labels)

            if all_labels:
                label_freq = Counter(all_labels)

                plt.figure(figsize=(12, 8))
                wordcloud = WordCloud(width=800, height=400, background_color='white',
                                      max_words=50, contour_width=3, contour_color='steelblue')
                wordcloud.generate_from_frequencies(label_freq)

                plt.imshow(wordcloud, interpolation='bilinear')
                plt.axis('off')
                plt.title('Issue Labels Wordcloud')
                plt.savefig(f'{output_dir}/issue_labels_wordcloud.png', dpi=300, bbox_inches='tight')
                plt.close()

        # 4. Comments count distribution
        if 'comments_count' in self.df.columns:
            plt.figure(figsize=(12, 5))

            plt.subplot(1, 2, 1)
            # Comments count distribution (log scale)
            comments_data = self.df[self.df['comments_count'] > 0]['comments_count']
            if len(comments_data) > 0:
                plt.hist(np.log1p(comments_data), bins=30, alpha=0.7, color='skyblue')
                plt.title('Comments Count Distribution (Log Scale)')
                plt.xlabel('log(Comments Count + 1)')
                plt.ylabel('Frequency')

            plt.subplot(1, 2, 2)
            # Comments count box plot
            plt.boxplot(comments_data, vert=False)
            plt.title('Comments Count Box Plot')
            plt.xlabel('Comments Count')

            plt.tight_layout()
            plt.savefig(f'{output_dir}/comments_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()

        logger.info(f"Visualization charts saved to {output_dir} directory")

    def save_analysis_report(self, output_file: str = "analysis_report.txt"):
        """Save analysis report"""
        import sys

        # Redirect output to file
        original_stdout = sys.stdout
        with open(output_file, 'w', encoding='utf-8') as f:
            sys.stdout = f

            # Rerun analysis
            self.basic_statistics()
            self.temporal_analysis()
            self.label_analysis()
            self.user_analysis()
            self.comments_analysis()

            sys.stdout = original_stdout

        logger.info(f"Analysis report saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Analyze GitHub Issue data')
    parser.add_argument('--data-file', default='issues_data.json',
                        help='Issue data file path (JSON or CSV)')
    parser.add_argument('--output-dir', default='plots',
                        help='Chart output directory')
    parser.add_argument('--report-file', default='analysis_report.txt',
                        help='Analysis report output file')

    args = parser.parse_args()

    # Create analyzer
    analyzer = IssueAnalyzer(args.data_file)

    # Execute analysis
    analyzer.basic_statistics()
    analyzer.temporal_analysis()
    analyzer.label_analysis(top_n=20)
    analyzer.user_analysis(top_n=15)
    analyzer.comments_analysis()

    # Create visualizations
    analyzer.create_visualizations(args.output_dir)

    # Save analysis report
    analyzer.save_analysis_report(args.report_file)

    print(f"\nAnalysis completed! Results saved.")
    print(f"- Analysis report: {args.report_file}")
    print(f"- Charts directory: {args.output_dir}")


if __name__ == "__main__":
    main()