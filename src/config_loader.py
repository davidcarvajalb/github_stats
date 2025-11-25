import os
import yaml
from datetime import datetime
from dotenv import load_dotenv

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

    def get_skip_users(self):
        return self.config.get("skip_users", [])

    def get_metrics(self):
        return self.config.get("metrics", [])

    def get_output_file(self):
        return self.config.get("output_file")

    def get_sort_by(self):
        return self.config.get("sort_by", "pr_created")

    def get_print_to_terminal(self):
        return self.config.get("print_to_terminal", False)
