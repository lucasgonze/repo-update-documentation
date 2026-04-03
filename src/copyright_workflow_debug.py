import json
import subprocess
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

# DEBUG MODE - Set to True to enable verbose logging
DEBUG = True

def debug_log(msg):
    """Print debug messages if DEBUG mode is enabled."""
    if DEBUG:
        print(f"[DEBUG] {msg}")

class CopyrightWorkflow:
    def __init__(self, config_path="repos-config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        # Use build/ directory under project root for all temporary files
        self.build_dir = Path("build")
        self.repos_dir = self.build_dir / "repos"

        # Create dated output directory structure
        date_str = datetime.now().strftime("%B-%d-%Y")  # e.g., "April-03-2026"
        self.output_package_dir = self.build_dir / f"Copyright-Registration-Updates-{date_str}"
        self.output_dir = self.output_package_dir / "Diffs"

        self.errors = []
        self.warnings = []
        print(f"Using build directory: {self.build_dir.absolute()}")
        print(f"Output package: {self.output_package_dir.name}")

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

            debug_log(f"Processing repo {idx+1}: {name} ({starting_commit}..{ending_commit})")

            if not repo_path.exists():
                self.log_error(f"Repository {name} path does not exist.")
                continue

            # Generate unique filename for this entry
            repo_counts[name] = repo_counts.get(name, 0) + 1
            if repo_counts[name] > 1:
                diff_file = self.output_dir / f"{name.replace('/', '_')}_{repo_counts[name]}.diff"
            else:
                diff_file = self.output_dir / f"{name.replace('/', '_')}.diff"

            debug_log(f"  Output file: {diff_file}")

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

            debug_log(f"  Filtered lines: {len(filtered_lines)}")

            if filtered_lines:
                with open(diff_file, 'w') as f:
                    f.write("\n".join(filtered_lines))
                debug_log(f"  Wrote {len(filtered_lines)} lines to {diff_file}")
                self.log_success(f"Generated diff for {name} ({starting_commit}..{ending_commit})")
            else:
                self.log_warning(f"No new authorship found for {name} ({starting_commit}..{ending_commit})")

        with open(self.output_dir / "README.txt", "w") as f:
            f.write("\n".join(readme_content))
        debug_log(f"Wrote README.txt with {len(readme_content)} lines")

    def create_archive(self):
        """Combines diffs into a PDF and Zips the output folder."""
        self.log_info("\n=== Creating Archive ===")

        # Generate date-based filename
        date_str = datetime.now().strftime("%m-%d-%Y")  # e.g., "04-03-2026"
        combined_filename = f"All-Updates-{date_str}.txt"
        pdf_filename = f"All-Updates-{date_str}.pdf"

        combined_path = self.output_package_dir / combined_filename

        debug_log(f"Output directory: {self.output_dir}")
        debug_log(f"Combined path: {combined_path}")

        # List all diff files before processing
        diff_files = list(self.output_dir.glob("*.diff"))
        debug_log(f"Found {len(diff_files)} diff files:")
        for df in diff_files:
            file_size = df.stat().st_size
            debug_log(f"  - {df.name} ({file_size} bytes)")

        # Combine everything for the PDF
        debug_log("Opening combined_path for writing...")
        with open(combined_path, 'w') as outfile:
            readme = self.output_dir / "README.txt"
            if readme.exists():
                readme_content = readme.read_text()
                readme_lines = len(readme_content.splitlines())
                debug_log(f"Writing README.txt ({readme_lines} lines)...")
                outfile.write(readme_content + "\n")
            else:
                debug_log("WARNING: README.txt does not exist!")

            # Process each diff file
            for idx, f in enumerate(self.output_dir.glob("*.diff")):
                debug_log(f"Processing diff file {idx+1}: {f.name}")

                header = f"\n{'='*80}\nFILE: {f.name}\n{'='*80}\n"
                debug_log(f"  Writing header: {repr(header)}")
                outfile.write(header)

                diff_content = f.read_text()
                diff_lines = len(diff_content.splitlines())
                debug_log(f"  Reading {diff_lines} lines from {f.name}")
                debug_log(f"  First 100 chars: {repr(diff_content[:100])}")
                outfile.write(diff_content)
                debug_log(f"  Wrote diff content for {f.name}")

                # Force flush to ensure data is written
                outfile.flush()
                debug_log(f"  Flushed output buffer")

        # Check what was actually written
        combined_size = combined_path.stat().st_size
        with open(combined_path, 'r') as f:
            combined_lines = len(f.readlines())
        debug_log(f"Combined file stats: {combined_lines} lines, {combined_size} bytes")

        # Show first and last few lines
        with open(combined_path, 'r') as f:
            all_lines = f.readlines()
            debug_log(f"First 5 lines of combined file:")
            for i, line in enumerate(all_lines[:5]):
                debug_log(f"  {i+1}: {repr(line[:80])}")
            debug_log(f"Last 5 lines of combined file:")
            for i, line in enumerate(all_lines[-5:]):
                debug_log(f"  {len(all_lines)-5+i+1}: {repr(line[:80])}")

        # Count how many "FILE:" markers are in the combined file
        with open(combined_path, 'r') as f:
            file_markers = sum(1 for line in f if line.startswith("FILE:"))
        debug_log(f"Found {file_markers} FILE: markers in combined output")

        # Attempt PDF generation via cupsfilter
        pdf_path = self.output_package_dir / pdf_filename
        if shutil.which("cupsfilter"):
            try:
                debug_log("Generating PDF with cupsfilter...")
                debug_log(f"Input file size: {combined_path.stat().st_size} bytes")

                # Run cupsfilter and capture stderr for debugging
                result = subprocess.run(
                    ["cupsfilter", str(combined_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )

                # Write the PDF output
                with open(pdf_path, "wb") as pdf_file:
                    pdf_file.write(result.stdout)

                pdf_size = pdf_path.stat().st_size
                debug_log(f"PDF generated: {pdf_size} bytes")

                # Check if PDF seems too small
                txt_size = combined_path.stat().st_size
                if pdf_size < txt_size * 0.1:  # PDF should be at least 10% of text size
                    debug_log(f"WARNING: PDF size ({pdf_size}) seems too small compared to text ({txt_size})")
                    debug_log(f"cupsfilter stderr: {result.stderr.decode('utf-8', errors='replace')}")
                    self.log_warning(f"PDF may be incomplete (only {pdf_size} bytes from {txt_size} bytes text)")
                else:
                    self.log_success(f"Generated {pdf_filename}")

                # If stderr had content, show it
                if result.stderr:
                    debug_log(f"cupsfilter stderr: {result.stderr.decode('utf-8', errors='replace')}")

            except Exception as e:
                debug_log(f"PDF generation exception: {e}")
                self.log_warning(f"PDF generation failed: {e}")
        else:
            debug_log("cupsfilter not found, skipping PDF generation")

        # Create Zip of the entire package directory
        zip_base_path = str(self.build_dir / self.output_package_dir.name)
        debug_log(f"Creating zip archive: {zip_base_path}.zip")
        debug_log(f"Archiving directory: {self.output_package_dir}")
        shutil.make_archive(zip_base_path, "zip", root_dir=self.build_dir, base_dir=self.output_package_dir.name)
        zip_size = Path(f"{zip_base_path}.zip").stat().st_size
        debug_log(f"Zip created: {zip_size} bytes")
        self.log_success(f"Generated {self.output_package_dir.name}.zip")

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
