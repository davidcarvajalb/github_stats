import os
import yaml
import requests
import pandas as pd
from github import Github, Auth
from datetime import datetime

class RateLimitExceededError(Exception):
    pass




class GitHubStatsFetcher:
    def __init__(self, token):
        auth = Auth.Token(token)
        # Disable automatic retries to prevent getting stuck on 403/Access Denied
        self.github = Github(auth=auth, retry=0)
        self.token = token

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

    def run_graphql_query(self, query, variables):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"GraphQL query failed with code {response.status_code}: {response.text}")

    def fetch_stats(self, repos, users=None, start_date=None, end_date=None, skip_labels=None):
        data = []
        if skip_labels is None:
            skip_labels = ["release"]
        
        # GraphQL query to fetch PRs and all nested data in one go
        # Reduced page size to 20 to avoid complexity limits when fetching nested comments
        query = """
        query($search_query: String!, $after: String) {
          search(query: $search_query, type: ISSUE, first: 20, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              ... on PullRequest {
                number
                number
                createdAt
                mergedAt
                author {
                  login
                }
                repository {
                    name
                    owner {
                        login
                    }
                }
                additions
                deletions
                labels(first: 20) {
                  nodes {
                    name
                  }
                }
                reviews(first: 50) {
                  nodes {
                    author {
                      login
                    }
                    state
                  }
                }
                comments(first: 50) {
                  nodes {
                    author {
                      login
                    }
                    createdAt
                  }
                }
                reviewThreads(first: 50) {
                  nodes {
                    comments(first: 50) {
                        nodes {
                            author {
                                login
                            }
                            createdAt
                        }
                    }
                  }
                }
              }
            }
          }
        }
        """

        for repo_name in repos:


            print(f"Fetching data for {repo_name} (via GraphQL)...")
            
            # Construct search query
            # Note: GraphQL search query format is same as REST
            # Ensure dates are formatted as YYYY-MM-DD to avoid spaces in query
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            search_query = f"repo:{repo_name} is:pr created:{start_str}..{end_str}"
            
            has_next_page = True
            after_cursor = None
            total_fetched = 0
            
            try:
                while has_next_page:
                    variables = {"search_query": search_query, "after": after_cursor}
                    result = self.run_graphql_query(query, variables)
                    
                    if "errors" in result:
                        # Handle GraphQL errors (like rate limits or access denied)
                        error_msg = result['errors'][0]['message']
                        print(f"\n  [Error] GraphQL Error for {repo_name}: {error_msg}")
                        
                        if "API rate limit exceeded" in error_msg:
                            raise RateLimitExceededError(f"Critical Error: {error_msg}")

                        # If it's a NOT_FOUND or FORBIDDEN, we might want to skip

                        break
                        
                    search_data = result['data']['search']
                    nodes = search_data['nodes']
                    page_info = search_data['pageInfo']
                    has_next_page = page_info['hasNextPage']
                    after_cursor = page_info['endCursor']
                    
                    for node in nodes:
                        if not node: # Sometimes nodes can be None
                            continue
                            
                        # Extract data
                        pr_number = node['number']
                        author_login = node['author']['login'] if node['author'] else "unknown"
                        created_at = datetime.strptime(node['createdAt'], "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Labels
                        labels = [l['name'].lower() for l in node['labels']['nodes']]
                        should_skip_lines = any(skip_label in labels for skip_label in skip_labels)
                        
                        additions = 0 if should_skip_lines else node['additions']
                        deletions = 0 if should_skip_lines else node['deletions']
                        
                        # 1. PR Creation
                        data.append({
                            "type": "pr_created",
                            "user": author_login,
                            "repo": repo_name,
                            "created_at": created_at,
                            "count": 1,
                            "additions": additions,
                            "deletions": deletions
                        })
                        
                        # 2. Reviews
                        if node['reviews']['nodes']:
                            # Track unique reviewers per PR to avoid double counting if they reviewed multiple times?
                            # The query returns all reviews. A user might approve after requesting changes.
                            # For simplicity, we'll count all distinct review actions or just the latest?
                            # GitHub's API returns all reviews.
                            # Let's count every significant action.
                            
                            for review in node['reviews']['nodes']:
                                if not review['author']:
                                    continue
                                    
                                reviewer_login = review['author']['login']
                                state = review['state']
                                
                                if state == 'APPROVED':
                                    data.append({
                                        "type": "review_approved",
                                        "user": reviewer_login,
                                        "repo": repo_name,
                                        "created_at": created_at,
                                        "count": 1
                                    })
                                elif state == 'CHANGES_REQUESTED':
                                    data.append({
                                        "type": "review_changes_requested",
                                        "user": reviewer_login,
                                        "repo": repo_name,
                                        "created_at": created_at,
                                        "count": 1
                                    })
                                elif state == 'COMMENTED':
                                    data.append({
                                        "type": "review_commented",
                                        "user": reviewer_login,
                                        "repo": repo_name,
                                        "created_at": created_at,
                                        "count": 1
                                    })

                        # 3. Merge Time
                        if node.get('mergedAt'):
                            merged_at = datetime.strptime(node['mergedAt'], "%Y-%m-%dT%H:%M:%SZ")
                            merge_time_hours = (merged_at - created_at).total_seconds() / 3600
                            data.append({
                                "type": "pr_merged",
                                "user": author_login,
                                "repo": repo_name,
                                "created_at": merged_at,
                                "merge_time_hours": merge_time_hours,
                                "count": 1
                            })
                        
                        # 3. Comments
                        # Issue comments
                        if node['comments']['nodes']:
                            for comment in node['comments']['nodes']:
                                if comment['author']:
                                    data.append({
                                        "type": "comment",
                                        "user": comment['author']['login'],
                                        "repo": repo_name,
                                        "created_at": datetime.strptime(comment['createdAt'], "%Y-%m-%dT%H:%M:%SZ"),
                                        "count": 1
                                    })
                        
                        # Review comments (sum of comments in threads)
                        if node['reviewThreads']['nodes']:
                            for thread in node['reviewThreads']['nodes']:
                                if thread['comments']['nodes']:
                                    for comment in thread['comments']['nodes']:
                                        if comment['author']:
                                            data.append({
                                                "type": "comment",
                                                "user": comment['author']['login'],
                                                "repo": repo_name,
                                                "created_at": datetime.strptime(comment['createdAt'], "%Y-%m-%dT%H:%M:%SZ"),
                                                "count": 1
                                            }) 

                    total_fetched += len(nodes)
                    print(f"  Fetched {total_fetched} PRs...", end="\r")
                
                print(f"\n  Finished processing {repo_name}.")

            except RateLimitExceededError:
                raise
            except Exception as e:
                print(f"\n  [Error] Error fetching {repo_name}: {e}")
                
        return pd.DataFrame(data)
