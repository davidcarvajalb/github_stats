# GitHub Stats Generator

A powerful Python tool to analyze GitHub repository activity and generate developer productivity reports.

## 🚀 Quick Start

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up Token**:
    - Copy `.env.example` to `.env`.
    - Add your GitHub Personal Access Token (PAT) to `.env`.

3.  **Configure**:
    - Copy `config.yaml.example` to `config.yaml`.
    - Edit `config.yaml` to set your Organization or Repositories and Date Range.

4.  **Run**:
    ```bash
    python stats.py
    ```

---

## 📊 Features

-   **Deep Insights**: Goes beyond basic counts to measure collaboration and velocity.
-   **GraphQL Powered**: Fast and efficient data fetching using GitHub's GraphQL API.
-   **Auto-Discovery**: Automatically finds all repositories in an organization.
-   **Smart Filtering**: Excludes bots and specific users automatically.
-   **Exportable**: Saves reports to Markdown for easy sharing.

## 📈 Metrics Explained

The script generates a table with the following columns:

| Metric | Description |
| :--- | :--- |
| **PRs Created** | Number of Pull Requests authored by the user. |
| **Reviews: Approved** | Number of reviews where the user explicitly approved a PR. |
| **Reviews: Changes Req.** | Number of reviews where the user requested changes (high rigor). |
| **Reviews: Commented** | Number of formal reviews left with comments (feedback without explicit approval). |
| **Total Comments** | Total volume of individual comments left on issues and PRs. |
| **Avg PR Size (loc)** | Average lines of code changed (additions + deletions) per PR. Smaller is generally better. |
| **Avg Merge Time (h)** | Average time in hours from PR creation to merge. Lower means higher velocity. |

## ⚙️ Configuration (`config.yaml`)

The script is highly configurable. Here are the key sections:

### 1. Scope
Define what to analyze. You can list specific repos or scan an entire org.
```yaml
organization: "YourOrg" # Optional: Auto-discover repos
repositories:           # Optional: Manual list
  - "owner/repo1"
```

### 2. Timeframe
```yaml
start_date: "2023-01-01"
end_date: "2023-12-31"
```

### 3. Filtering
Exclude noise from your report.
```yaml
skip_users:
  - "dependabot[bot]"
skip_labels:
  - "release" # Exclude PRs with these labels from size calculations
```

### 4. Output Customization
Control what you see.
```yaml
metrics: [pr_created, reviews_approved, comments, avg_merge_time]
sort_by: "pr_created"
output_file: "report.md"
print_to_terminal: true
```

## 🛠️ Troubleshooting

-   **403/404 Errors**: If the script hits a permission error or a missing repo, it will log the error and continue.
-   **Rate Limits**: The script uses GraphQL to minimize API calls, but large organizations may still take some time.
