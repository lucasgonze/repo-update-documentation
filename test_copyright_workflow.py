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
        """Test archive creation when cupsfilter is available."""
        mock_which.return_value = "/usr/bin/cupsfilter"

        # Mock glob to find one .diff file and mock read_text for README
        with patch("pathlib.Path.glob", return_value=[Path("test.diff")]):
            with patch("pathlib.Path.read_text", return_value="README content\n"):
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

if __name__ == "__main__":
    unittest.main()
