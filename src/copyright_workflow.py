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
        # Use build/ directory under project root for all temporary files
        self.build_dir = Path("build")
        self.repos_dir = self.build_dir / "repos"
        self.output_dir = self.build_dir / "diffs"
        self.errors = []
        self.warnings = []
        print(f"Using build directory: {self.build_dir.absolute()}")

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
        self.repos_dir.mkdir(parents=True, exist_ok=True)

        # Track which repos we've already synced to avoid duplicates
        synced_repos = set()

        for repo in self.config.get("repositories", []):
            name, url = repo["name"], repo["url"]
            repo_path = self.repos_dir / name

            # Skip if we've already synced this repo
            if name in synced_repos:
                continue
            synced_repos.add(name)

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

        # Track counts for duplicate repo names to create unique filenames
        repo_counts = {}

        for idx, repo in enumerate(self.config.get("repositories", [])):
            name = repo["name"]
            starting_commit = repo["starting_commit"]
            ending_commit = repo.get("ending_commit", "HEAD")
            repo_path = self.repos_dir / name

            if not repo_path.exists():
                self.log_error(f"Repository {name} path does not exist.")
                continue

            # Generate unique filename for this entry
            repo_counts[name] = repo_counts.get(name, 0) + 1
            if repo_counts[name] > 1:
                diff_file = self.output_dir / f"{name.replace('/', '_')}_{repo_counts[name]}.diff"
            else:
                diff_file = self.output_dir / f"{name.replace('/', '_')}.diff"

            # Resolve ending_commit to actual hash
            ending_hash_res = self.run_git(["rev-parse", ending_commit], cwd=repo_path)
            if ending_hash_res.returncode != 0:
                self.log_error(f"Failed to resolve {ending_commit} for {name}: {ending_hash_res.stderr}")
                continue
            ending_hash = ending_hash_res.stdout.strip()

            # Metadata for README
            readme_content.append(f"# Repository: {name}\nStarting={starting_commit}\nEnding={ending_hash}\n")

            # 1. Create the full diff
            res = self.run_git(["diff", starting_commit, ending_hash], cwd=repo_path)

            if res.returncode != 0:
                self.log_error(f"Failed to generate diff for {name}: {res.stderr}")
                continue

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
                self.log_success(f"Generated diff for {name} ({starting_commit}..{ending_commit})")
            else:
                self.log_warning(f"No new authorship found for {name} ({starting_commit}..{ending_commit})")

        with open(self.output_dir / "README.txt", "w") as f:
            f.write("\n".join(readme_content))

    def create_archive(self):
        """Combines diffs into a PDF and Zips the output folder."""
        self.log_info("\n=== Creating Archive ===")
        combined_path = self.build_dir / "runlog.txt"

        # Combine everything for the PDF
        with open(combined_path, 'w') as outfile:
            readme = self.output_dir / "README.txt"
            if readme.exists():
                outfile.write(readme.read_text() + "\n")

            for f in self.output_dir.glob("*.diff"):
                outfile.write(f"\n{'='*80}\nFILE: {f.name}\n{'='*80}\n")
                outfile.write(f.read_text())

        # Attempt PDF generation via cupsfilter
        pdf_path = self.build_dir / "runlog.pdf"
        if shutil.which("cupsfilter"):
            try:
                with open(pdf_path, "wb") as pdf_file:
                    subprocess.run(["cupsfilter", str(combined_path)], stdout=pdf_file, check=True, stderr=subprocess.DEVNULL)
                self.log_success("Generated runlog.pdf")
            except Exception as e:
                self.log_warning(f"PDF generation failed: {e}")

        # Create Zip
        zip_path = str(self.build_dir / "runlog")
        shutil.make_archive(zip_path, "zip", self.output_dir)
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
