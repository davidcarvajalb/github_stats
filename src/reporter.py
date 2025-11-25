from tabulate import tabulate

class StatsReporter:
    def __init__(self, df, users_filter=None, skip_users=None, metrics=None, output_file=None, sort_by=None, print_to_terminal=False):
        self.df = df
        self.users_filter = users_filter
        self.skip_users = skip_users
        self.metrics = metrics
        self.output_file = output_file
        self.sort_by = sort_by
        self.print_to_terminal = print_to_terminal

    def generate_report(self):
        output_buffer = []
        
        def print_out(text):
            if self.print_to_terminal:
                print(text)
            output_buffer.append(text)

        if self.df.empty:
            print_out("No data found.")
            self._save_output(output_buffer)
            return

        # Filter by users if provided (inclusion)
        if self.users_filter:
            self.df = self.df[self.df['user'].isin(self.users_filter)]

        # Filter by skip_users (exclusion)
        if self.skip_users:
            self.df = self.df[~self.df['user'].isin(self.skip_users)]

        if self.df.empty:
            print_out("No data found after filtering by users.")
            self._save_output(output_buffer)
            return

        # Get unique repositories
        repositories = self.df['repo'].unique()
        
        for repo in repositories:
            repo_df = self.df[self.df['repo'] == repo]
            
            if repo_df.empty:
                continue
                
            # Aggregate by user and type for this repo
            summary = repo_df.groupby(['user', 'type'])['count'].sum().unstack(fill_value=0)
            
            # Aggregate additions/deletions for pr_created type (for Avg PR Size)
            pr_created_df = repo_df[repo_df['type'] == 'pr_created']
            if not pr_created_df.empty:
                # Sum additions and deletions
                lines_stats = pr_created_df.groupby('user')[['additions', 'deletions']].sum()
                # Count PRs
                pr_counts = pr_created_df.groupby('user')['count'].sum()
                
                # Calculate Avg PR Size
                # We need to join first to ensure alignment
                size_df = pd.DataFrame({'total_lines': lines_stats['additions'] + lines_stats['deletions'], 'pr_count': pr_counts})
                size_df['avg_pr_size'] = size_df['total_lines'] / size_df['pr_count']
                
                summary = summary.join(size_df[['avg_pr_size']], how='left').fillna(0)
            else:
                summary['avg_pr_size'] = 0

            # Aggregate Merge Time
            pr_merged_df = repo_df[repo_df['type'] == 'pr_merged']
            if not pr_merged_df.empty:
                # Average merge time
                merge_stats = pr_merged_df.groupby('user')['merge_time_hours'].mean()
                summary = summary.join(merge_stats, how='left').fillna(0)
                summary = summary.rename(columns={'merge_time_hours': 'avg_merge_time'})
            else:
                summary['avg_merge_time'] = 0
            
            # Rename columns
            column_mapping = {
                'pr_created': 'PRs Created',
                'review_approved': 'Reviews: Approved',
                'review_changes_requested': 'Reviews: Changes Req.',
                'review_commented': 'Reviews: Commented',
                'comment': 'Total Comments',
                'avg_pr_size': 'Avg PR Size (loc)',
                'avg_merge_time': 'Avg Merge Time (h)'
            }
            summary = summary.rename(columns=column_mapping)
            
            # Ensure all expected columns exist
            all_cols = [
                'PRs Created', 
                'Reviews: Approved', 
                'Reviews: Changes Req.', 
                'Reviews: Commented', 
                'Total Comments', 
                'Avg PR Size (loc)', 
                'Avg Merge Time (h)'
            ]
            for col in all_cols:
                if col not in summary.columns:
                    summary[col] = 0
            
            # Round floats
            summary['Avg PR Size (loc)'] = summary['Avg PR Size (loc)'].round(0).astype(int)
            summary['Avg Merge Time (h)'] = summary['Avg Merge Time (h)'].round(1)
            
            # Filter columns based on metrics config
            if self.metrics:
                # Map config keys to column names
                metric_map = {
                    'pr_created': 'PRs Created',
                    'reviews_approved': 'Reviews: Approved',
                    'reviews_changes_requested': 'Reviews: Changes Req.',
                    'reviews_commented': 'Reviews: Commented',
                    'comments': 'Total Comments',
                    'avg_pr_size': 'Avg PR Size (loc)',
                    'avg_merge_time': 'Avg Merge Time (h)'
                }
                selected_cols = [metric_map[m] for m in self.metrics if m in metric_map]
                # Always keep columns that exist in summary
                final_cols = [c for c in selected_cols if c in summary.columns]
                if not final_cols:
                    print_out(f"Warning: No valid metrics found for {repo}. Defaulting to all.")
                    final_cols = all_cols
            else:
                final_cols = all_cols

            # Select and reorder columns
            summary = summary[final_cols]
            
            # Filter out users with no activity (all zeros)
            # We check if the sum of all columns is > 0
            summary = summary[summary.sum(axis=1) > 0]
            
            if summary.empty:
                continue
            
            # Convert float columns to int (except merge time)
            # summary = summary.astype(int) # Can't do this globally anymore due to floats
            int_cols = [c for c in summary.columns if c != 'Avg Merge Time (h)']
            summary[int_cols] = summary[int_cols].astype(int)
            
            # Sort by configured column
            if not summary.empty:
                # Default map
                metric_map = {
                    'pr_created': 'PRs Created',
                    'reviews_approved': 'Reviews: Approved',
                    'reviews_changes_requested': 'Reviews: Changes Req.',
                    'reviews_commented': 'Reviews: Commented',
                    'comments': 'Total Comments',
                    'avg_pr_size': 'Avg PR Size (loc)',
                    'avg_merge_time': 'Avg Merge Time (h)'
                }
                
                sort_col = metric_map.get(self.sort_by, 'PRs Created')
                if sort_col in summary.columns:
                    summary = summary.sort_values(sort_col, ascending=False)
                else:
                    # Fallback to first column
                    first_col = summary.columns[0]
                    summary = summary.sort_values(first_col, ascending=False)
            
            # Reset index to make User a column for printing
            summary = summary.reset_index()
            
            print_out(f"\nStats for {repo}:")
            print_out(tabulate(summary, headers='keys', tablefmt='github', showindex=False))
            print_out("") # Add newline
            
        self._save_output(output_buffer)

    def _save_output(self, buffer):
        if self.output_file:
            try:
                with open(self.output_file, "w") as f:
                    f.write("\n".join(buffer))
                print(f"\nReport saved to {self.output_file}")
            except Exception as e:
                print(f"\nError saving report to file: {e}")
