import json
import subprocess
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

class CopyrightWorkflow:
    def __init__(self, config_path="repos-config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.repos_dir = Path(self.config.get("repos_dir", "repos"))
        self.output_dir = Path(self.config.get("output_dir", "diffs"))
        self.errors = []
        self.warnings = []

    def _load_config(self):
        """Loads repository configuration from JSON."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file {self.config_path} not found.")
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def log_info(self, msg): print(f"{msg}")
    def log_success(self, msg): print(f"\033[92mSUCCESS: {msg}\033[0m")
    def log_warning(self, msg):
        print(f"\033[93mWARNING: {msg}\033[0m")
        self.warnings.append(msg)
    def log_error(self, msg):
        print(f"\033[91mERROR: {msg}\033[0m")
        self.errors.append(msg)

    def run_git(self, args, cwd=None):
        """Helper to run git commands."""
        return subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False
        )

    def sync_repositories(self):
        """Clones or updates repositories listed in config."""
        self.log_info("=== Syncing Repositories ===")
        self.repos_dir.mkdir(exist_ok=True)
        
        for repo in self.config.get("repositories", []):
            name, url = repo["name"], repo["url"]
            repo_path = self.repos_dir / name

            if not repo_path.exists():
                self.log_info(f"Cloning {name}...")
                res = self.run_git(["clone", url, str(repo_path)])
                if res.returncode != 0:
                    self.log_error(f"Failed to clone {name}: {res.stderr}")
            else:
                self.log_info(f"Updating {name}...")
                # Attempt to move to a default branch and pull
                self.run_git(["checkout", "main"], cwd=repo_path)
                self.run_git(["pull"], cwd=repo_path)
        print()

    def generate_diffs(self):
        """Generates filtered diffs for Copyright Office submission."""
        self.log_info("=== Generating Diffs ===")
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)

        readme_content = [f"Diffs recorded {datetime.now()}\n"]

        for repo in self.config.get("repositories", []):
            name = repo["name"]
            prev_hash = repo["last_registered_commit"]
            repo_path = self.repos_dir / name
            diff_file = self.output_dir / f"{name.replace('/', '_')}.diff"

            if not repo_path.exists():
                self.log_error(f"Repository {name} path does not exist.")
                continue

            # Metadata for README
            curr_hash = self.run_git(["rev-parse", "HEAD"], cwd=repo_path).stdout.strip()
            readme_content.append(f"# Repository: {name}\nCurrent={curr_hash}\nPrevious={prev_hash}\n")

            # 1. Create the full diff
            res = self.run_git(["diff", prev_hash, "HEAD"], cwd=repo_path)
            
            # 2. BUSINESS LOGIC: Filter out deletions
            # We skip lines starting with '-' unless it's the '---' file header.
            filtered_lines = []
            for line in res.stdout.splitlines():
                if line.startswith('-') and not line.startswith('---'):
                    continue
                filtered_lines.append(line)

            if filtered_lines:
                with open(diff_file, 'w') as f:
                    f.write("\n".join(filtered_lines))
                self.log_success(f"Generated diff for {name}")
            else:
                self.log_warning(f"No new authorship found for {name}")

        with open(self.output_dir / "README.txt", "w") as f:
            f.write("\n".join(readme_content))

    def create_archive(self):
        """Combines diffs into a PDF and Zips the output folder."""
        self.log_info("\n=== Creating Archive ===")
        combined_path = Path("runlog.txt")
        
        # Combine everything for the PDF
        with open(combined_path, 'w') as outfile:
            readme = self.output_dir / "README.txt"
            if readme.exists():
                outfile.write(readme.read_text() + "\n")
            
            for f in self.output_dir.glob("*.diff"):
                outfile.write(f"\n{'='*80}\nFILE: {f.name}\n{'='*80}\n")
                outfile.write(f.read_text())

        # Attempt PDF generation via cupsfilter
        if shutil.which("cupsfilter"):
            try:
                with open("runlog.pdf", "wb") as pdf_file:
                    subprocess.run(["cupsfilter", str(combined_path)], stdout=pdf_file, check=True, stderr=subprocess.DEVNULL)
                self.log_success("Generated runlog.pdf")
            except Exception as e:
                self.log_warning(f"PDF generation failed: {e}")

        # Create Zip
        shutil.make_archive("runlog", "zip", self.output_dir)
        self.log_success("Generated runlog.zip")

    def run(self, mode="full"):
        if mode in ["check", "full"]:
            self.sync_repositories()
        if mode in ["diff", "full"]:
            self.generate_diffs()
            self.create_archive()
        
        self.log_info("\n=== Summary ===")
        if self.errors: self.log_error(f"{len(self.errors)} errors encountered.")
        else: self.log_success("Workflow completed successfully!")

if __name__ == "__main__":
    import sys
    app = CopyrightWorkflow()
    # Support basic mode switching like the bash script
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    app.run(mode=run_mode)
