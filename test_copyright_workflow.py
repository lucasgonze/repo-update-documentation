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
                    "last_registered_commit": "abc1234"
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
        # Repo dir doesn't exist, then specific repo doesn't exist
        mock_exists.side_effect = [True, False] 
        mock_run.return_value = MagicMock(returncode=0)

        self.workflow.sync_repositories()
        
        # Verify clone was called
        mock_run.assert_any_call(
            ["git", "clone", self.config_data["repositories"][0]["url"], "test_repos/test-repo"],
            cwd=None, capture_output=True, text=True, check=False
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_sync_repositories_update(self, mock_exists, mock_run):
        """Test updating a repo when it already exists."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        self.workflow.sync_repositories()
        
        # Verify pull was called
        mock_run.assert_any_call(
            ["git", "pull"],
            cwd=Path("test_repos/test-repo"), capture_output=True, text=True, check=False
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_diffs_success(self, mock_file, mock_mkdir, mock_rmtree, mock_exists, mock_run):
        """Test successful diff generation and filtering logic."""
        mock_exists.return_value = True
        
        # Mock git rev-parse and git diff
        diff_output = "--- a/file.txt\n+++ b/file.txt\n-deleted line\n+added line\n"
        mock_run.side_effect = [
            MagicMock(stdout="curr_hash_123", returncode=0), # rev-parse
            MagicMock(stdout=diff_output, returncode=0)      # diff
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
        """Test archive creation when cupsfilter is available."""
        mock_which.return_value = "/usr/bin/cupsfilter"
        
        # Mock glob to find one .diff file
        with patch("pathlib.Path.glob", return_value=[Path("test.diff")]):
            self.workflow.create_archive()

        # Verify PDF conversion was attempted
        mock_run.assert_any_call(
            ["cupsfilter", "runlog.txt"],
            stdout=unittest.mock.ANY, check=True, stderr=unittest.mock.ANY
        )
        mock_zip.assert_called_once()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.which", return_value=None)
    @patch("shutil.make_archive")
    def test_create_archive_no_pdf(self, mock_zip, mock_which, mock_exists):
        """Test archive creation when cupsfilter is missing (fallback to text)."""
        with patch("pathlib.Path.glob", return_value=[]):
            with patch("builtins.open", mock_open()):
                self.workflow.create_archive()
        
        self.assertIn("PDF generation failed", str(self.workflow.warnings) if self.workflow.warnings else "")

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

if __name__ == "__main__":
    unittest.main()
