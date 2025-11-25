from src.config_loader import ConfigLoader
from src.fetcher import GitHubStatsFetcher
from src.reporter import StatsReporter

def main():
    try:
        loader = ConfigLoader()
        loader.load()
        
        fetcher = GitHubStatsFetcher(loader.token)
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
        skip_users = loader.get_skip_users()
        metrics = loader.get_metrics()
        output_file = loader.get_output_file()
        sort_by = loader.get_sort_by()
        print_to_terminal = loader.get_print_to_terminal()
        
        # We don't pass users anymore, as we discover them
        df = fetcher.fetch_stats(repos, None, start_date, end_date, skip_labels)
        
        reporter = StatsReporter(df, skip_users=skip_users, metrics=metrics, output_file=output_file, sort_by=sort_by, print_to_terminal=print_to_terminal)
        reporter.generate_report()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
