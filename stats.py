import os
import yaml
import pandas as pd
from github import Github, Auth, GithubException
from dotenv import load_dotenv
from datetime import datetime
from tabulate import tabulate

class ConfigLoader:
    def __init__(self, config_path="config.yaml", env_path=".env"):
        self.config_path = config_path
        self.env_path = env_path
        self.config = {}
        self.token = None

    def load(self):
        load_dotenv(self.env_path)
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN not found in environment variables.")

        if not os.path.exists(self.config_path):
             raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        # Validate config
        if "repositories" not in self.config and "organization" not in self.config:
            raise ValueError("Config must have 'repositories' list or 'organization'.")
        
        # Parse dates
        if "start_date" in self.config:
            self.config["start_date"] = datetime.strptime(self.config["start_date"], "%Y-%m-%d")
        if "end_date" in self.config:
            self.config["end_date"] = datetime.strptime(self.config["end_date"], "%Y-%m-%d")

    def get_repos(self):
        return self.config.get("repositories", [])

    def get_users(self):
        return self.config.get("users", [])
    
    def get_date_range(self):
        return self.config.get("start_date"), self.config.get("end_date")

    def get_organization(self):
        return self.config.get("organization")

    def get_skip_labels(self):
        return [l.lower() for l in self.config.get("skip_labels", ["release"])]


class SkippedReposManager:
    def __init__(self, filepath="skipped_repos.yaml"):
        self.filepath = filepath
        self.skipped_repos = self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            return []
        try:
            with open(self.filepath, "r") as f:
                data = yaml.safe_load(f)
                return data.get("skipped_repos", []) if data else []
        except Exception as e:
            print(f"Warning: Could not load skipped repos file: {e}")
            return []

    def save(self):
        try:
            with open(self.filepath, "w") as f:
                yaml.dump({"skipped_repos": self.skipped_repos}, f)
        except Exception as e:
            print(f"Warning: Could not save skipped repos file: {e}")

    def add(self, repo_name):
        if repo_name not in self.skipped_repos:
            self.skipped_repos.append(repo_name)
            self.save()
            print(f"  [Info] Added {repo_name} to skipped_repos.yaml")

    def is_skipped(self, repo_name):
        return repo_name in self.skipped_repos


class GitHubStatsFetcher:
    def __init__(self, token, skipped_manager=None):
        auth = Auth.Token(token)
        # Disable automatic retries to prevent getting stuck on 403/Access Denied
        self.github = Github(auth=auth, retry=0)
        self.skipped_manager = skipped_manager

    def fetch_org_repos(self, org_name):
        print(f"Fetching repositories for organization: {org_name}...")
        try:
            org = self.github.get_organization(org_name)
            repos = []
            for repo in org.get_repos():
                repos.append(repo.full_name)
            print(f"  Found {len(repos)} repositories in {org_name}.")
            return repos
        except Exception as e:
            print(f"Error fetching org repos: {e}")
            return []

    def fetch_stats(self, repos, users=None, start_date=None, end_date=None, skip_labels=None):
        data = []
        if skip_labels is None:
            skip_labels = ["release"]
        
        for repo_name in repos:
            if self.skipped_manager and self.skipped_manager.is_skipped(repo_name):
                print(f"Skipping {repo_name} (found in skipped_repos.yaml)...")
                continue

            print(f"Fetching data for {repo_name}...")
            try:
                repo = self.github.get_repo(repo_name)
                
                # Construct search query
                query = f"repo:{repo_name} is:pr"
                
                if start_date and end_date:
                    query += f" created:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
                elif start_date:
                    query += f" created:>={start_date.strftime('%Y-%m-%d')}"
                elif end_date:
                    query += f" created:<={end_date.strftime('%Y-%m-%d')}"
                
                # We do NOT filter by user here anymore, as we want to discover them
                
                print(f"  Query: {query}")
                issues = self.github.search_issues(query)
                total_issues = issues.totalCount
                print(f"  Found {total_issues} PRs to process.")
                
                for i, issue in enumerate(issues, 1):
                    if i == 1:
                        print(f"  [Debug] First PR found created at: {issue.created_at}")

                    if not issue.pull_request:
                        continue
                    
                    print(f"  Processing PR {i}/{total_issues} (#{issue.number}) by {issue.user.login}...", end="\r")
                    
                    # Get the PR object for reviews and comments
                    pr = issue.as_pull_request()
                    
                    # Check for skip labels to skip line counts
                    labels = [l.name.lower() for l in issue.labels]
                    should_skip_lines = any(skip_label in labels for skip_label in skip_labels)
                    
                    additions = 0 if should_skip_lines else pr.additions
                    deletions = 0 if should_skip_lines else pr.deletions
                    
                    if should_skip_lines:
                         print(f"    (Skipping lines for PR #{issue.number} with skip labels)", end="\r")

                    # 1. PR Creation Data
                    data.append({
                        "type": "pr_created",
                        "user": issue.user.login,
                        "repo": repo_name,
                        "created_at": issue.created_at,
                        "count": 1,
                        "additions": additions,
                        "deletions": deletions
                    })
                    
                    # 2. Approvals
                    reviews = pr.get_reviews()
                    for review in reviews:
                        if review.state == 'APPROVED':
                            data.append({
                                "type": "pr_approved",
                                "user": review.user.login,
                                "repo": repo_name,
                                "created_at": review.submitted_at, # Use review date
                                "count": 1
                            })
                            
                    # 3. Comments (Issue Comments + Review Comments)
                    # Issue comments (general conversation)
                    for comment in issue.get_comments():
                        data.append({
                            "type": "comment",
                            "user": comment.user.login,
                            "repo": repo_name,
                            "created_at": comment.created_at,
                            "count": 1
                        })
                        
                    # Review comments (code comments)
                    for comment in pr.get_review_comments():
                        data.append({
                            "type": "comment",
                            "user": comment.user.login,
                            "repo": repo_name,
                            "created_at": comment.created_at,
                            "count": 1
                        })
                
                print(f"\n  Finished processing {repo_name}.")

            except GithubException as e:
                if e.status == 403:
                    print(f"\n  [Warning] Access Denied or Rate Limit hit for {repo_name} (403). Skipping and adding to ignore list.")
                    if self.skipped_manager:
                        self.skipped_manager.add(repo_name)
                elif e.status == 404:
                    print(f"\n  [Warning] Repository {repo_name} not found (404). Skipping and adding to ignore list.")
                    if self.skipped_manager:
                        self.skipped_manager.add(repo_name)
                else:
                    print(f"\n  [Error] GitHub API Error for {repo_name}: {e}")
            except Exception as e:
                print(f"\n  [Error] Error fetching {repo_name}: {e}")
                
        return pd.DataFrame(data)

class StatsReporter:
    def __init__(self, data, users_filter=None):
        self.df = data
        self.users_filter = users_filter

    def generate_report(self):
        if self.df.empty:
            print("No data found.")
            return

        # Filter by users if provided
        if self.users_filter:
            self.df = self.df[self.df['user'].isin(self.users_filter)]

        if self.df.empty:
            print("No data found after filtering by users.")
            return

        # Get unique repositories
        repositories = self.df['repo'].unique()
        
        for repo in repositories:
            repo_df = self.df[self.df['repo'] == repo]
            
            if repo_df.empty:
                continue
                
            # Aggregate by user and type for this repo
            summary = repo_df.groupby(['user', 'type'])['count'].sum().unstack(fill_value=0)
            
            # Aggregate additions/deletions for pr_created type
            pr_created_df = repo_df[repo_df['type'] == 'pr_created']
            if not pr_created_df.empty:
                lines_stats = pr_created_df.groupby('user')[['additions', 'deletions']].sum()
                summary = summary.join(lines_stats, how='left').fillna(0)
            else:
                summary['additions'] = 0
                summary['deletions'] = 0
            
            # Rename columns
            column_mapping = {
                'pr_created': 'PRs Created',
                'pr_approved': 'PRs Approved',
                'comment': 'Total Comments',
                'additions': 'Lines Added',
                'deletions': 'Lines Removed'
            }
            summary = summary.rename(columns=column_mapping)
            
            # Ensure all expected columns exist
            expected_cols = ['PRs Created', 'PRs Approved', 'Total Comments', 'Lines Added', 'Lines Removed']
            for col in expected_cols:
                if col not in summary.columns:
                    summary[col] = 0
                    
            # Select and reorder columns
            summary = summary[expected_cols]
            
            # Filter out users with no activity (all zeros)
            # We check if the sum of all columns is > 0
            summary = summary[summary.sum(axis=1) > 0]
            
            if summary.empty:
                continue
            
            # Convert float columns to int
            summary = summary.astype(int)
            
            # Sort by PRs Created descending
            summary = summary.sort_values('PRs Created', ascending=False)
            
            # Reset index to make User a column for printing
            summary = summary.reset_index()
            
            print(f"\nStats for {repo}:")
            print(tabulate(summary, headers='keys', tablefmt='github', showindex=False))

def main():
    try:
        loader = ConfigLoader()
        loader.load()
        
        skipped_manager = SkippedReposManager()
        fetcher = GitHubStatsFetcher(loader.token, skipped_manager)
        repos = loader.get_repos()
        if repos is None:
            repos = []
            
        org_name = loader.get_organization()
        if org_name:
            org_repos = fetcher.fetch_org_repos(org_name)
            # Avoid duplicates
            repos = list(set(repos + org_repos))
            
        if not repos:
            print("No repositories found to process.")
            return

        start_date, end_date = loader.get_date_range()
        skip_labels = loader.get_skip_labels()
        
        # We don't pass users anymore, as we discover them
        df = fetcher.fetch_stats(repos, None, start_date, end_date, skip_labels)
        
        reporter = StatsReporter(df)
        reporter.generate_report()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
