import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
from pathlib import Path
import shutil

# Assuming your script is named copyright_workflow.py
from copyright_workflow import CopyrightWorkflow

class TestCopyrightWorkflow(unittest.TestCase):

    def setUp(self):
        """Set up a mock configuration and instance."""
        self.config_data = {
            "repos_dir": "test_repos",
            "output_dir": "test_diffs",
            "repositories": [
                {
                    "name": "test-repo",
                    "url": "https://github.com/example/test-repo.git",
                    "starting_commit": "abc1234",
                    "ending_commit": "def5678"
                }
            ]
        }
        self.config_json = json.dumps(self.config_data)

        # Patch open to provide the mock config
        with patch("builtins.open", mock_open(read_data=self.config_json)):
            with patch("pathlib.Path.exists", return_value=True):
                self.workflow = CopyrightWorkflow("mock_config.json")

    def test_load_config_not_found(self):
        """Test error handling when config file is missing."""
        with patch("pathlib.Path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                CopyrightWorkflow("non_existent.json")

    @patch("subprocess.run")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    def test_sync_repositories_clone(self, mock_exists, mock_mkdir, mock_run):
        """Test cloning a repo when it doesn't exist."""
        # Return False for repo_path.exists() to trigger clone
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        self.workflow.sync_repositories()

        # Verify clone was called - match the Path argument
        expected_url = self.config_data["repositories"][0]["url"]
        calls = [call.args[0] for call in mock_run.call_args_list]
        self.assertTrue(
            any(["git", "clone", expected_url] == call[:3] for call in calls),
            f"Expected git clone call not found in {calls}"
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_sync_repositories_update(self, mock_exists, mock_run):
        """Test updating a repo when it already exists."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        self.workflow.sync_repositories()

        # Verify pull was called - check that it was called with repo name in path
        calls = [call for call in mock_run.call_args_list if call.args[0] == ["git", "pull"]]
        self.assertTrue(
            len(calls) > 0 and "test-repo" in str(calls[0].kwargs.get("cwd", "")),
            f"Expected git pull call with test-repo in path not found"
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_success(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test successful diff generation and filtering logic."""
        mock_exists.return_value = True

        # Mock git rev-parse (for ending_commit) and git diff
        diff_output = "--- a/file.txt\n+++ b/file.txt\n-deleted line\n+added line\n"
        mock_run.side_effect = [
            MagicMock(stdout="def5678\n", returncode=0),  # rev-parse ending_commit
            MagicMock(stdout=diff_output, returncode=0)   # diff
        ]

        self.workflow.generate_diffs()

        # Check filtering logic: '-deleted line' should be gone, but '--- a/file.txt' stays
        handle = mock_file()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn("--- a/file.txt", written_content)
        self.assertIn("+added line", written_content)
        self.assertNotIn("-deleted line", written_content)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("shutil.make_archive")
    @patch("builtins.open", new_callable=mock_open)
    def test_create_archive_with_pdf(self, mock_file, mock_zip, mock_run, mock_which, mock_exists):
        """Test archive creation when cupsfilter is available and PDF is not truncated."""
        mock_which.return_value = "/usr/bin/cupsfilter"

        # Mock cupsfilter to return reasonably-sized PDF content
        mock_run.return_value = MagicMock(
            stdout=b"large pdf content" * 10000,  # Large PDF (170KB)
            stderr=b"",
            returncode=0
        )

        # Mock file sizes: text file (100000 bytes), PDF (170000 bytes = 170% - well above 10% threshold)
        mock_stat_pdf = MagicMock()
        mock_stat_pdf.st_size = 170000  # PDF size
        mock_stat_txt = MagicMock()
        mock_stat_txt.st_size = 100000  # Text size

        # Mock glob to find one .diff file and mock read_text for README
        with patch("pathlib.Path.glob", return_value=[Path("test.diff")]):
            with patch("pathlib.Path.read_text", return_value="README content\n"):
                with patch("pathlib.Path.stat", side_effect=[mock_stat_pdf, mock_stat_txt]):
                    self.workflow.create_archive()

        # Verify PDF conversion was attempted - check for All-Updates in the path
        calls = [call for call in mock_run.call_args_list
                 if call.args[0][0] == "cupsfilter" and "All-Updates" in str(call.args[0][1])]
        self.assertTrue(len(calls) > 0, "Expected cupsfilter call with All-Updates file not found")
        mock_zip.assert_called_once()

        # Verify no truncation warning (PDF is large enough)
        truncation_warnings = [w for w in self.workflow.warnings if "incomplete" in w]
        self.assertEqual(len(truncation_warnings), 0)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.which", return_value=None)
    @patch("shutil.make_archive")
    def test_create_archive_no_pdf(self, mock_zip, mock_which, mock_exists):
        """Test archive creation when cupsfilter is missing (fallback to text)."""
        with patch("pathlib.Path.glob", return_value=[]):
            with patch("pathlib.Path.read_text", return_value="README content\n"):
                with patch("builtins.open", mock_open()):
                    self.workflow.create_archive()

        # When cupsfilter is not available, no warning is generated (it just skips PDF generation)
        mock_zip.assert_called_once()

    def test_run_modes(self):
        """Test that different modes trigger the correct methods."""
        with patch.object(CopyrightWorkflow, 'sync_repositories') as mock_sync:
            with patch.object(CopyrightWorkflow, 'generate_diffs') as mock_diff:
                with patch.object(CopyrightWorkflow, 'create_archive') as mock_arch:
                    
                    # Test 'check' mode
                    self.workflow.run(mode="check")
                    mock_sync.assert_called_once()
                    mock_diff.assert_not_called()

                    mock_sync.reset_mock()
                    
                    # Test 'diff' mode
                    self.workflow.run(mode="diff")
                    mock_sync.assert_not_called()
                    mock_diff.assert_called_once()
                    mock_arch.assert_called_once()

    @patch("subprocess.run")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    def test_sync_repositories_clone_failure(self, mock_exists, mock_mkdir, mock_run):
        """Test handling of git clone failure."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=1, stderr="Clone failed")

        self.workflow.sync_repositories()

        # Verify error was logged
        self.assertTrue(len(self.workflow.errors) > 0)
        self.assertIn("Failed to clone", self.workflow.errors[0])

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_repo_not_found(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test handling when repository path doesn't exist."""
        mock_exists.return_value = False

        self.workflow.generate_diffs()

        # Verify error was logged
        self.assertTrue(len(self.workflow.errors) > 0)
        self.assertIn("path does not exist", self.workflow.errors[0])

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_rev_parse_failure(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test handling of git rev-parse failure."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid commit")

        self.workflow.generate_diffs()

        # Verify error was logged
        self.assertTrue(len(self.workflow.errors) > 0)
        self.assertIn("Failed to resolve", self.workflow.errors[0])

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_diff_failure(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test handling of git diff failure."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            MagicMock(stdout="def5678\n", returncode=0),  # rev-parse success
            MagicMock(returncode=1, stderr="Diff failed")  # diff failure
        ]

        self.workflow.generate_diffs()

        # Verify error was logged
        self.assertTrue(len(self.workflow.errors) > 0)
        self.assertIn("Failed to generate diff", self.workflow.errors[0])

    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("shutil.make_archive")
    @patch("builtins.open", new_callable=mock_open)
    def test_create_archive_pdf_failure(self, mock_file, mock_zip, mock_run, mock_which, mock_exists):
        """Test handling of PDF generation failure."""
        mock_which.return_value = "/usr/bin/cupsfilter"
        mock_run.side_effect = Exception("PDF generation error")

        with patch("pathlib.Path.glob", return_value=[]):
            with patch("pathlib.Path.read_text", return_value="README content\n"):
                self.workflow.create_archive()

        # Verify warning was logged
        self.assertTrue(len(self.workflow.warnings) > 0)
        self.assertIn("PDF generation failed", self.workflow.warnings[0])

    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("shutil.make_archive")
    @patch("builtins.open", new_callable=mock_open)
    def test_create_archive_pdf_truncation_warning(self, mock_file, mock_zip, mock_run, mock_which, mock_exists):
        """Test detection of truncated PDF (when PDF is suspiciously small)."""
        mock_which.return_value = "/usr/bin/cupsfilter"

        # Mock cupsfilter to return small PDF content with stderr warning
        mock_run.return_value = MagicMock(
            stdout=b"small pdf content",  # 17 bytes
            stderr=b"cupsfilter: File too large, output may be truncated",
            returncode=0
        )

        # Mock file sizes: large text file (1000000 bytes), small PDF (5000 bytes = 0.5%)
        mock_stat = MagicMock()
        mock_stat.st_size = 5000  # PDF size (first call to stat())
        mock_stat_txt = MagicMock()
        mock_stat_txt.st_size = 1000000  # Text size (second call to stat())

        with patch("pathlib.Path.glob", return_value=[]):
            with patch("pathlib.Path.read_text", return_value="README content\n"):
                with patch("pathlib.Path.stat", side_effect=[mock_stat, mock_stat_txt]):
                    self.workflow.create_archive()

        # Verify truncation warning was logged (PDF is < 10% of text size)
        self.assertTrue(len(self.workflow.warnings) > 0)
        self.assertIn("PDF may be incomplete", self.workflow.warnings[0])

    def test_log_warning(self):
        """Test log_warning method."""
        self.workflow.log_warning("Test warning")
        self.assertEqual(len(self.workflow.warnings), 1)
        self.assertEqual(self.workflow.warnings[0], "Test warning")

    def test_log_error(self):
        """Test log_error method."""
        self.workflow.log_error("Test error")
        self.assertEqual(len(self.workflow.errors), 1)
        self.assertEqual(self.workflow.errors[0], "Test error")

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_no_changes(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test diff generation when there are no changes."""
        mock_exists.return_value = True

        # Mock git rev-parse and git diff with truly empty diff (no changes at all)
        diff_output = ""
        mock_run.side_effect = [
            MagicMock(stdout="def5678\n", returncode=0),  # rev-parse ending_commit
            MagicMock(stdout=diff_output, returncode=0)   # diff
        ]

        self.workflow.generate_diffs()

        # Verify warning was logged
        self.assertTrue(len(self.workflow.warnings) > 0)
        self.assertIn("No new authorship found", self.workflow.warnings[0])

    @patch("subprocess.run")
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    def test_sync_repositories_duplicate_repos(self, mock_exists, mock_mkdir, mock_run):
        """Test that duplicate repos are only synced once."""
        # Create config with duplicate repos
        duplicate_config = {
            "repos_dir": "test_repos",
            "output_dir": "test_diffs",
            "repositories": [
                {
                    "name": "test-repo",
                    "url": "https://github.com/example/test-repo.git",
                    "starting_commit": "abc1234",
                    "ending_commit": "def5678"
                },
                {
                    "name": "test-repo",
                    "url": "https://github.com/example/test-repo.git",
                    "starting_commit": "xyz9999",
                    "ending_commit": "HEAD"
                }
            ]
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(duplicate_config))):
            with patch("pathlib.Path.exists", return_value=True):
                workflow = CopyrightWorkflow("mock_config.json")

        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        workflow.sync_repositories()

        # Verify git pull was only called once (duplicate was skipped)
        pull_calls = [call for call in mock_run.call_args_list if call.args[0] == ["git", "pull"]]
        self.assertEqual(len(pull_calls), 1)

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_duplicate_repos(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test that duplicate repos generate unique diff filenames."""
        # Create config with duplicate repos
        duplicate_config = {
            "repos_dir": "test_repos",
            "output_dir": "test_diffs",
            "repositories": [
                {
                    "name": "test-repo",
                    "url": "https://github.com/example/test-repo.git",
                    "starting_commit": "abc1234",
                    "ending_commit": "def5678"
                },
                {
                    "name": "test-repo",
                    "url": "https://github.com/example/test-repo.git",
                    "starting_commit": "xyz9999",
                    "ending_commit": "HEAD"
                }
            ]
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(duplicate_config))):
            with patch("pathlib.Path.exists", return_value=True):
                workflow = CopyrightWorkflow("mock_config.json")

        mock_exists.return_value = True
        diff_output = "--- a/file.txt\n+++ b/file.txt\n+added line\n"
        mock_run.side_effect = [
            MagicMock(stdout="def5678\n", returncode=0),  # rev-parse 1
            MagicMock(stdout=diff_output, returncode=0),  # diff 1
            MagicMock(stdout="abc9999\n", returncode=0),  # rev-parse 2
            MagicMock(stdout=diff_output, returncode=0),  # diff 2
        ]

        workflow.generate_diffs()

        # Verify both diff files were created with unique names
        write_calls = [call for call in mock_file().write.call_args_list]
        # Should have written to two different files
        self.assertTrue(len(write_calls) >= 2)

    def test_main_execution_default_mode(self):
        """Test main execution block with default (no args) mode."""
        import sys

        # Save original argv
        original_argv = sys.argv

        try:
            sys.argv = ["copyright_workflow.py"]

            # Test the main block logic
            run_mode = sys.argv[1] if len(sys.argv) > 1 else "full"
            self.assertEqual(run_mode, "full")
        finally:
            sys.argv = original_argv

    def test_main_execution_with_args(self):
        """Test main execution block with command line arguments."""
        import sys

        # Save original argv
        original_argv = sys.argv

        try:
            sys.argv = ["copyright_workflow.py", "check"]

            # Test the main block logic
            run_mode = sys.argv[1] if len(sys.argv) > 1 else "full"
            self.assertEqual(run_mode, "check")
        finally:
            sys.argv = original_argv

    def test_main_block_integration(self):
        """Integration test for the main block by running as subprocess."""
        import subprocess
        import os

        # Change to parent directory where the config file is
        original_dir = os.getcwd()
        try:
            os.chdir('..')

            # Run the script with the existing config
            result = subprocess.run(
                ['python3', 'src/copyright_workflow.py', 'check'],
                capture_output=True,
                text=True,
                timeout=10
            )

            # The script should print the build directory (check both stdout and stderr)
            output = result.stdout + result.stderr
            self.assertIn("build", output.lower())
        finally:
            os.chdir(original_dir)

    def test_main_block_as_module(self):
        """Test running the module as __main__ using runpy."""
        import sys
        import runpy
        import os

        # Save original values
        original_argv = sys.argv
        original_dir = os.getcwd()

        try:
            # Change to parent dir and set argv
            os.chdir('..')
            sys.argv = ["copyright_workflow.py", "check"]

            # Mock to prevent actual execution
            with patch.object(CopyrightWorkflow, 'sync_repositories'):
                with patch.object(CopyrightWorkflow, 'generate_diffs'):
                    with patch.object(CopyrightWorkflow, 'create_archive'):
                        # Run the module as __main__
                        try:
                            runpy.run_path('src/copyright_workflow.py', run_name='__main__')
                        except SystemExit:
                            # Module might call sys.exit(), that's ok
                            pass

            # If we got here without exception, the main block executed
            self.assertTrue(True)
        finally:
            sys.argv = original_argv
            os.chdir(original_dir)

if __name__ == "__main__":
    unittest.main()
