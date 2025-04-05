import subprocess
from typing import Optional, List, NamedTuple
from pathlib import Path
from unittest.mock import MagicMock, patch, call # Use patch from unittest.mock

import git # Import for type hinting and exceptions
import pytest

# Functions to test
from shared.utils import git_utils
# Helper class for mocking subprocess.run result
class MockCompletedProcess(NamedTuple):
    stdout: str
    stderr: str
    returncode: int = 0

# --- Tests for run_git_command ---

@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch('subprocess.run', autospec=True) as mock_run:
        yield mock_run

def test_run_git_command_success(mock_subprocess_run, tmp_path):
    """Test run_git_command with a successful command execution."""
    command = "git status"
    expected_stdout = "On branch main\nYour branch is up to date with 'origin/main'."
    mock_subprocess_run.return_value = MockCompletedProcess(stdout=expected_stdout, stderr="")

    result = git_utils.run_git_command(command, tmp_path)

    assert result == expected_stdout
    mock_subprocess_run.assert_called_once_with(
        command, shell=True, cwd=tmp_path, check=True, capture_output=True,
        text=True, encoding='utf-8', errors='ignore'
    )

def test_run_git_command_success_with_stderr(mock_subprocess_run, tmp_path, caplog):
    """Test successful command execution that produces stderr output (warnings)."""
    command = "git fetch"
    expected_stdout = "Fetching origin"
    warning_stderr = "warning: some warning message"
    mock_subprocess_run.return_value = MockCompletedProcess(stdout=expected_stdout, stderr=warning_stderr)

    result = git_utils.run_git_command(command, tmp_path)

    assert result == expected_stdout
    assert warning_stderr in caplog.text # Check if warning was logged
    mock_subprocess_run.assert_called_once()

def test_run_git_command_failure_called_process_error(mock_subprocess_run, tmp_path):
    """Test run_git_command when the command fails (CalledProcessError)."""
    command = "git invalid-command"
    error_stderr = "fatal: 'invalid-command' is not a git command."
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=command, stderr=error_stderr
    )

    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        git_utils.run_git_command(command, tmp_path)

    assert error_stderr in str(excinfo.value.stderr) # Check error message propagation
    mock_subprocess_run.assert_called_once()

def test_run_git_command_failure_file_not_found(mock_subprocess_run, tmp_path):
    """Test run_git_command when git executable is not found."""
    command = "git status"
    mock_subprocess_run.side_effect = FileNotFoundError("git command not found")

    with pytest.raises(FileNotFoundError):
        git_utils.run_git_command(command, tmp_path)

    mock_subprocess_run.assert_called_once()

def test_run_git_command_failure_other_exception(mock_subprocess_run, tmp_path):
    """Test run_git_command with an unexpected exception."""
    command = "git status"
    mock_subprocess_run.side_effect = Exception("Unexpected OS error")

    with pytest.raises(Exception, match="Unexpected OS error"):
        git_utils.run_git_command(command, tmp_path)

    mock_subprocess_run.assert_called_once()

# --- Tests for find_commit_hash_before_timestamp ---

@patch('shared.utils.git_utils.run_git_command', autospec=True)
def test_find_commit_timestamp_found(mock_run_cmd, tmp_path):
    """Test finding a commit hash successfully."""
    timestamp = 1678886400 # Example timestamp
    expected_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    mock_run_cmd.return_value = f"{expected_hash}\n" # Simulate git output with newline

    result = git_utils.find_commit_hash_before_timestamp(tmp_path, timestamp)

    assert result == expected_hash
    expected_cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=tmp_path)

@patch('shared.utils.git_utils.run_git_command', autospec=True)
def test_find_commit_timestamp_not_found_empty_output(mock_run_cmd, tmp_path):
    """Test when no commit exists before the timestamp (empty output)."""
    timestamp = 1000 # Very early timestamp
    mock_run_cmd.return_value = "" # Simulate git returning nothing

    result = git_utils.find_commit_hash_before_timestamp(tmp_path, timestamp)

    assert result is None
    expected_cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=tmp_path)

@patch('shared.utils.git_utils.run_git_command', autospec=True)
def test_find_commit_timestamp_not_found_invalid_hash(mock_run_cmd, tmp_path):
    """Test when git returns something, but it's not a valid hash."""
    timestamp = 1678886400
    mock_run_cmd.return_value = "not-a-hash"

    result = git_utils.find_commit_hash_before_timestamp(tmp_path, timestamp)

    assert result is None
    expected_cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=tmp_path)

@patch('shared.utils.git_utils.run_git_command', autospec=True)
def test_find_commit_timestamp_called_process_error(mock_run_cmd, tmp_path):
    """Test handling CalledProcessError from run_git_command."""
    timestamp = 1678886400
    mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "git rev-list", stderr="fatal: bad revision 'HEAD'")

    result = git_utils.find_commit_hash_before_timestamp(tmp_path, timestamp)

    assert result is None
    expected_cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=tmp_path)

@patch('shared.utils.git_utils.run_git_command', autospec=True)
def test_find_commit_timestamp_other_exception(mock_run_cmd, tmp_path):
    """Test handling other exceptions from run_git_command."""
    timestamp = 1678886400
    mock_run_cmd.side_effect = Exception("Some other error")

    result = git_utils.find_commit_hash_before_timestamp(tmp_path, timestamp)

    assert result is None
    expected_cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=tmp_path)

# --- Tests for checkout_commit ---

@pytest.fixture
def mock_repo():
    """Fixture to create a MagicMock git.Repo object."""
    repo = MagicMock(spec=git.Repo)
    # Mock the 'git' attribute which is used to call raw commands
    repo.git = MagicMock()
    return repo

def test_checkout_commit_success(mock_repo):
    """Test successful checkout."""
    commit_hash = "a1b2c3d4e5f6"

    result = git_utils.checkout_commit(mock_repo, commit_hash)

    assert result is True
    # Verify that the sequence of git commands was called
    mock_repo.git.reset.assert_called_once_with('--hard')
    mock_repo.git.clean.assert_called_once_with('-fdx')
    mock_repo.git.checkout.assert_called_once_with(commit_hash, force=True)

def test_checkout_commit_git_command_error(mock_repo):
    """Test checkout failure due to GitCommandError."""
    commit_hash = "a1b2c3d4e5f6"
    mock_repo.git.checkout.side_effect = git.GitCommandError(
        "checkout", 1, stderr=f"pathspec '{commit_hash}' did not match any file(s) known to git"
    )

    result = git_utils.checkout_commit(mock_repo, commit_hash)

    assert result is False
    # reset and clean should still be called
    mock_repo.git.reset.assert_called_once_with('--hard')
    mock_repo.git.clean.assert_called_once_with('-fdx')
    mock_repo.git.checkout.assert_called_once_with(commit_hash, force=True)

def test_checkout_commit_other_exception(mock_repo):
    """Test checkout failure due to an unexpected exception."""
    commit_hash = "a1b2c3d4e5f6"
    mock_repo.git.checkout.side_effect = Exception("Unexpected error")

    result = git_utils.checkout_commit(mock_repo, commit_hash)

    assert result is False
    # reset and clean should still be called
    mock_repo.git.reset.assert_called_once_with('--hard')
    mock_repo.git.clean.assert_called_once_with('-fdx')
    mock_repo.git.checkout.assert_called_once_with(commit_hash, force=True)

# --- Tests for determine_default_branch ---

# Helper to create mock refs
def create_mock_ref(name, is_symbolic=False, ref_name=None):
    ref = MagicMock(spec=git.RemoteReference)
    ref.name = name
    if is_symbolic:
        # Mock the .reference attribute for symbolic refs
        ref.reference = MagicMock(spec=git.RemoteReference)
        ref.reference.name = ref_name
    return ref

@pytest.fixture
def mock_repo_for_branch():
    """Fixture to create a mock repo specifically for branch determination."""
    repo = MagicMock(spec=git.Repo)
    repo.remotes.origin = MagicMock(spec=git.Remote)
    repo.heads = [] # Default to no local heads initially
    repo.remotes.origin.refs = [] # Default to no remote refs initially
    return repo

def test_determine_default_branch_finds_main(mock_repo_for_branch):
    """Test finding 'origin/main'."""
    mock_repo_for_branch.remotes.origin.refs = [
        create_mock_ref("origin/develop"),
        create_mock_ref("origin/main"),
        create_mock_ref("origin/master"),
    ]
    result = git_utils.determine_default_branch(mock_repo_for_branch)
    assert result == "origin/main"
    mock_repo_for_branch.remotes.origin.fetch.assert_not_called() # Should not fetch if refs exist

def test_determine_default_branch_finds_master(mock_repo_for_branch):
    """Test finding 'origin/master' when 'origin/main' is absent."""
    mock_repo_for_branch.remotes.origin.refs = [
        create_mock_ref("origin/develop"),
        create_mock_ref("origin/master"),
        create_mock_ref("origin/feature/x"),
    ]
    result = git_utils.determine_default_branch(mock_repo_for_branch)
    assert result == "origin/master"

def test_determine_default_branch_finds_via_head(mock_repo_for_branch):
    """Test finding the default branch via 'origin/HEAD' symbolic ref."""
    mock_repo_for_branch.remotes.origin.refs = [
        create_mock_ref("origin/develop"),
        create_mock_ref("origin/feature/y"),
        create_mock_ref("origin/HEAD", is_symbolic=True, ref_name="origin/develop"), # HEAD points to develop
    ]
    result = git_utils.determine_default_branch(mock_repo_for_branch)
    assert result == "origin/develop"

def test_determine_default_branch_fallback(mock_repo_for_branch):
    """Test fallback mechanism when common names and HEAD are absent."""
    mock_repo_for_branch.remotes.origin.refs = [
        create_mock_ref("origin/release/v1.0"),
        create_mock_ref("origin/feature/z"), # Sorted first alphabetically
    ]
    result = git_utils.determine_default_branch(mock_repo_for_branch)
    assert result == "origin/feature/z" # Falls back to the first sorted ref

def test_determine_default_branch_empty_repo_fetch(mock_repo_for_branch):
    """Test that fetch is called for an empty repo, then finds branch."""
    # Simulate fetch populating refs
    def mock_fetch(*args, **kwargs):
        mock_repo_for_branch.remotes.origin.refs = [
            create_mock_ref("origin/master"),
        ]
    mock_repo_for_branch.remotes.origin.fetch.side_effect = mock_fetch

    result = git_utils.determine_default_branch(mock_repo_for_branch)

    assert result == "origin/master"
    mock_repo_for_branch.remotes.origin.fetch.assert_called_once()

def test_determine_default_branch_no_refs_found(mock_repo_for_branch):
    """Test raising ValueError when no suitable ref is found after fetch."""
    # Simulate fetch not finding any suitable refs
    mock_repo_for_branch.remotes.origin.fetch.return_value = None

    with pytest.raises(ValueError, match="Failed to determine default branch."):
        git_utils.determine_default_branch(mock_repo_for_branch)

    mock_repo_for_branch.remotes.origin.fetch.assert_called_once() # Fetch should be called

def test_determine_default_branch_handles_git_error(mock_repo_for_branch):
    """Test raising ValueError when a GitCommandError occurs."""
    mock_repo_for_branch.remotes.origin.refs = [
        create_mock_ref("origin/main"),
    ]
    # Simulate an error during access (though less likely with mocks)
    mock_repo_for_branch.remotes.origin = MagicMock(side_effect=git.GitCommandError("fetch", 1, stderr="connection failed"))

    with pytest.raises(ValueError, match="Failed to determine default branch"):
        git_utils.determine_default_branch(mock_repo_for_branch)

def test_determine_default_branch_handles_attribute_error(mock_repo_for_branch):
    """Test raising ValueError when refs structure is unexpected."""
    # Simulate unexpected structure
    mock_repo_for_branch.remotes.origin.refs = None

    with pytest.raises(ValueError, match="Failed to determine default branch"):
        git_utils.determine_default_branch(mock_repo_for_branch)