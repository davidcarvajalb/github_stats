# GitHub Stats Generator

A Python script to generate statistics for GitHub repositories, including Pull Request counts, Approvals, and Comments per user.

## Features

- **Automatic User Discovery**: No need to manually list users; the script finds everyone who contributed.
- **Repository Auto-discovery**: Optionally fetch all repositories from a GitHub Organization.
- **Metrics**:
    - PRs Created
    - PRs Approved
    - Total Comments (Issues + Reviews)
    - Lines Added (excludes PRs with labels in `skip_labels`)
    - Lines Removed (excludes PRs with labels in `skip_labels`)
- **Date Filtering**: Analyze data within a specific date range.
- **Console Output**: Prints clean ASCII tables ready for sharing (e.g., in Slack).

## Prerequisites

- Python 3.x
- A GitHub Personal Access Token (PAT) with `repo` scope.

## Setup

1.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    # Linux/macOS (Bash/Zsh)
    source venv/bin/activate
    # Fish Shell
    source venv/bin/activate.fish
    # Windows
    .\venv\Scripts\activate
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    - Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    - Open `.env` and paste your GitHub Token:
        ```
        GITHUB_TOKEN=your_github_pat_here
        ```

4.  **Configure Script**:
    - Edit `config.yaml`:
        ```yaml
        # Option 1: List specific repositories
        repositories:
          - owner/repo1
          - owner/repo2

        # Option 2: Auto-discover from an Organization (can be used with or without 'repositories')
        organization: "YourOrgName"

        # Date range for the stats
        start_date: "2023-01-01"
        end_date: "2023-12-31"

        # Labels to skip for line count metrics (case-insensitive)
        skip_labels:
          - "release"
          - "dependencies"
        ```

    - **Skipped Repositories**: The script will automatically create a `skipped_repos.yaml` file to track repositories that return "Access Denied" (403) or "Not Found" (404) errors. These repositories will be skipped in future runs to save time. You can manually edit this file if needed.

## Usage

Run the script:
```bash
python stats.py
```

## Output Example

```text
Stats for owner/repo1:
| User      | PRs Created | PRs Approved | Total Comments | Lines Added | Lines Removed |
|-----------|-------------|--------------|----------------|-------------|---------------|
| user1     | 15          | 5            | 42             | 1500        | 500           |
| user2     | 10          | 12           | 20             | 800         | 200           |

Stats for owner/repo2:
| User      | PRs Created | PRs Approved | Total Comments | Lines Added | Lines Removed |
|-----------|-------------|--------------|----------------|-------------|---------------|
| user3     | 5           | 2            | 10             | 100         | 50            |
```
