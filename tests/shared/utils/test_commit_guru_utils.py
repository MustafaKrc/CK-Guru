import math
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import pandas as pd
import numpy as np # For NaN checks

# Import functions and classes to test
from shared.utils import commit_guru_utils
from shared.utils.commit_guru_utils import (
    _parse_commit_guru_log,
    _parse_numstat_line,
    _update_file_state,
    _update_dev_experience,
    _calculate_entropy,
    _finalize_metrics,
    calculate_commit_guru_metrics,
    GitCommitLinker,
    CommitFile, # Import helper classes if needed for state setup
    ParsedNumstatLine,
    FileUpdateResult,
    DevExperienceMetrics,
)

# Mock the logger to avoid actual logging during tests
# You can also use caplog fixture if you need to assert log messages
@pytest.fixture(autouse=True)
def mock_logging():
    with patch('shared.utils.commit_guru_utils.logger', MagicMock()):
        yield

# --- Sample Data ---

SAMPLE_GIT_LOG_OUTPUT_SINGLE = """
"<CAS_COMMIT_START><CAS_FIELD>parent_hashes<CAS_DELIM>p1h<CAS_END><CAS_FIELD>commit_hash<CAS_DELIM>c1h<CAS_END><CAS_FIELD>author_name<CAS_DELIM>Author One<CAS_END><CAS_FIELD>author_email<CAS_DELIM>one@example.com<CAS_END><CAS_FIELD>author_date<CAS_DELIM>Mon Apr 1 10:00:00 2024 +0000<CAS_END><CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>1711965600<CAS_END><CAS_FIELD>commit_message<CAS_DELIM>feat: Implement feature X

Add initial implementation.
Refs #123<CAS_END><CAS_COMMIT_END>
10\t5\tsrc/main.py
-\t-\tassets/logo.png
"""

SAMPLE_GIT_LOG_OUTPUT_MULTI = """
"<CAS_COMMIT_START><CAS_FIELD>parent_hashes<CAS_DELIM>p0h<CAS_END><CAS_FIELD>commit_hash<CAS_DELIM>c1h<CAS_END><CAS_FIELD>author_name<CAS_DELIM>Author One<CAS_END><CAS_FIELD>author_email<CAS_DELIM>one@example.com<CAS_END><CAS_FIELD>author_date<CAS_DELIM>Mon Apr 1 10:00:00 2024 +0000<CAS_END><CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>1711965600<CAS_END><CAS_FIELD>commit_message<CAS_DELIM>feat: Add feature X<CAS_END><CAS_COMMIT_END>
5\t2\tsrc/feature_x.py
"<CAS_COMMIT_START><CAS_FIELD>parent_hashes<CAS_DELIM>c1h<CAS_END><CAS_FIELD>commit_hash<CAS_DELIM>c2h<CAS_END><CAS_FIELD>author_name<CAS_DELIM>Author Two<CAS_END><CAS_FIELD>author_email<CAS_DELIM>two@example.com<CAS_END><CAS_FIELD>author_date<CAS_DELIM>Mon Apr 1 11:00:00 2024 +0000<CAS_END><CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>1711969200<CAS_END><CAS_FIELD>commit_message<CAS_DELIM>fix: Correct bug in feature X

Closes #45<CAS_END><CAS_COMMIT_END>
8\t3\tsrc/feature_x.py
2\t1\ttests/test_feature_x.py
"""

SAMPLE_GIT_LOG_EMPTY_STATS = """
"<CAS_COMMIT_START><CAS_FIELD>parent_hashes<CAS_DELIM>p1h<CAS_END><CAS_FIELD>commit_hash<CAS_DELIM>c1h<CAS_END><CAS_FIELD>author_name<CAS_DELIM>Author One<CAS_END><CAS_FIELD>author_email<CAS_DELIM>one@example.com<CAS_END><CAS_FIELD>author_date<CAS_DELIM>Mon Apr 1 10:00:00 2024 +0000<CAS_END><CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>1711965600<CAS_END><CAS_FIELD>commit_message<CAS_DELIM>chore: Update README<CAS_END><CAS_COMMIT_END>

""" # Note the empty line where stats would be

SAMPLE_DIFF_U0 = """
diff --git a/src/main.py b/src/main.py
index 123..456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -5,0 +5,2 @@ def old_func():
+    print("new line 1")
+    print("new line 2")
@@ -10 +12 @@ def another_func():
-    pass # removed line
@@ -15,0 +16,1 @@ def yet_another():
+    # added line
diff --git a/README.md b/README.md
index abc..def 100644
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-# Old Title
+# New Title
"""

SAMPLE_NAME_ONLY = """
src/main.py
README.md
"""

SAMPLE_BLAME_OUTPUT = """
a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2 10 10 1
author Author One
author-mail <one@example.com>
author-time 1700000000
author-tz +0000
committer Committer One
committer-mail <committer@example.com>
committer-time 1700000000
committer-tz +0000
summary Initial commit
previous b0b1b2b3b4b5b6b7b8b9b0b1b2b3b4b5b6b7b8b9 filename.py
filename src/main.py
\t    pass # removed line
f0e1d2c3b4a5f0e1d2c3b4a5f0e1d2c3b4a5f0e1 16 16 1
author Author Two
author-mail <two@example.com>
author-time 1710000000
author-tz +0000
committer Committer Two
committer-mail <committer@example.com>
committer-time 1710000000
committer-tz +0000
summary Add another func
filename src/main.py
\t    # added line
"""

# --- Tests for Helper Functions ---

def test_parse_commit_guru_log_single():
    """Test parsing a single commit entry."""
    result = _parse_commit_guru_log(SAMPLE_GIT_LOG_OUTPUT_SINGLE)
    assert len(result) == 1
    commit = result[0]
    assert commit['commit_hash'] == 'c1h'
    assert commit['parent_hashes'] == 'p1h'
    assert commit['author_name'] == 'Author One'
    assert commit['author_email'] == 'one@example.com'
    assert commit['author_date_unix_timestamp'] == '1711965600'
    assert 'Implement feature X' in commit['commit_message']
    assert 'Refs #123' in commit['commit_message']
    assert len(commit['stats_lines']) == 2
    assert commit['stats_lines'][0] == '10\t5\tsrc/main.py'
    assert commit['stats_lines'][1] == '-\t-\tassets/logo.png'

def test_parse_commit_guru_log_multi():
    """Test parsing multiple commit entries."""
    result = _parse_commit_guru_log(SAMPLE_GIT_LOG_OUTPUT_MULTI)
    assert len(result) == 2
    assert result[0]['commit_hash'] == 'c1h'
    assert result[1]['commit_hash'] == 'c2h'
    assert result[0]['stats_lines'][0] == '5\t2\tsrc/feature_x.py'
    assert result[1]['stats_lines'][0] == '8\t3\tsrc/feature_x.py'
    assert result[1]['stats_lines'][1] == '2\t1\ttests/test_feature_x.py'

def test_parse_commit_guru_log_empty_stats():
    """Test parsing a commit with no numstat output."""
    result = _parse_commit_guru_log(SAMPLE_GIT_LOG_EMPTY_STATS)
    assert len(result) == 1
    commit = result[0]
    assert commit['commit_hash'] == 'c1h'
    assert commit['stats_lines'] == [] # splitlines() on empty string is []

def test_parse_commit_guru_log_empty_input():
    """Test parsing empty git log output."""
    result = _parse_commit_guru_log("")
    assert len(result) == 0

def test_parse_commit_guru_log_malformed():
    """Test parsing malformed git log output."""
    malformed = "<CAS_COMMIT_START><CAS_FIELD>commit_hash<CAS_DELIM>c1h<CAS_END>" # Missing end tag
    result = _parse_commit_guru_log(malformed)
    assert len(result) == 0 # Should skip malformed blobs

def test_parse_numstat_line_added_deleted():
    """Test parsing a standard numstat line."""
    line = "10\t5\tsrc/main.py"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result == ParsedNumstatLine(la=10, ld=5, file_name='src/main.py', subsystem='src', directory='src')

def test_parse_numstat_line_added_only():
    """Test parsing a numstat line with only additions."""
    line = "15\t0\tnew_file.txt"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result == ParsedNumstatLine(la=15, ld=0, file_name='new_file.txt', subsystem='root', directory='root') # Directory is root if no /

def test_parse_numstat_line_deleted_only():
    """Test parsing a numstat line with only deletions."""
    line = "0\t7\tpath/to/old_file.java"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result == ParsedNumstatLine(la=0, ld=7, file_name='path/to/old_file.java', subsystem='path', directory='path/to')

def test_parse_numstat_line_binary():
    """Test parsing a numstat line for a binary file."""
    line = "-\t-\tassets/image.jpg"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result == ParsedNumstatLine(la=0, ld=0, file_name='assets/image.jpg', subsystem='assets', directory='assets')

def test_parse_numstat_line_malformed_parts():
    """Test parsing a line with incorrect number of tab-separated parts."""
    line = "10\t5" # Missing file path
    result = _parse_numstat_line(line, "dummy_hash")
    assert result is None

def test_parse_numstat_line_malformed_la_ld():
    """Test parsing a line with non-integer additions/deletions."""
    line = "abc\t5\tsrc/file.py"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result is None
    line = "10\txyz\tsrc/file.py"
    result = _parse_numstat_line(line, "dummy_hash")
    assert result is None

def test_parse_numstat_line_empty():
    """Test parsing an empty line."""
    line = ""
    result = _parse_numstat_line(line, "dummy_hash")
    assert result is None

# --- Tests for State Updates ---

def test_update_file_state_new_file():
    """Test updating state when a file is seen for the first time."""
    commit_files_state: Dict[str, CommitFile] = {}
    parsed_line = ParsedNumstatLine(la=10, ld=2, file_name='a.py', subsystem='a.py', directory='root')
    author = 'dev1'
    timestamp = 1000

    result = _update_file_state(parsed_line, author, timestamp, commit_files_state)

    # Check returned historical data (should be 0s for new file)
    assert result == FileUpdateResult(previous_loc=0, previous_nuc=0, time_diff_days=0.0, authors_involved={'dev1'})

    # Check state modification
    assert 'a.py' in commit_files_state
    file_state = commit_files_state['a.py']
    assert file_state.name == 'a.py'
    assert file_state.loc == 8 # 10 - 2
    assert file_state.authors == ['dev1']
    assert file_state.lastchanged == 1000
    assert file_state.nuc == 1 # Initial count is 1

def test_update_file_state_existing_file():
    """Test updating state for a file that exists."""
    commit_files_state: Dict[str, CommitFile] = {
        'a.py': CommitFile(name='a.py', loc=5, authors=['dev1'], lastchanged=500) # nuc defaults to 1
    }
    commit_files_state['a.py'].nuc = 3 # Set a previous nuc value

    parsed_line = ParsedNumstatLine(la=7, ld=1, file_name='a.py', subsystem='a.py', directory='root')
    author = 'dev2'
    timestamp = 1500 # 1000 seconds later

    result = _update_file_state(parsed_line, author, timestamp, commit_files_state)

    # Check returned historical data
    time_diff_expected = (1500 - 500) / 86400.0
    assert result.previous_loc == 5
    assert result.previous_nuc == 3
    assert math.isclose(result.time_diff_days, time_diff_expected)
    assert result.authors_involved == {'dev1'} # Authors *before* this commit

    # Check state modification
    assert 'a.py' in commit_files_state
    file_state = commit_files_state['a.py']
    assert file_state.loc == 11 # 5 + (7 - 1)
    assert set(file_state.authors) == {'dev1', 'dev2'} # Order doesn't matter, use set
    assert file_state.lastchanged == 1500
    assert file_state.nuc == 4 # 3 + 1

def test_update_dev_experience_new_author():
    """Test dev experience update for a new author."""
    dev_experience_state: Dict[str, Dict[str, int]] = {}
    author = 'dev1'
    subsystem = 'sub1'

    result = _update_dev_experience(author, subsystem, dev_experience_state)

    # Check returned historical data (0 for new author)
    assert result == DevExperienceMetrics(exp=0, rexp=0.0, sexp=0)

    # Check state modification
    assert dev_experience_state == {'dev1': {'sub1': 1}}

def test_update_dev_experience_existing_author_same_subsystem():
    """Test dev experience update for existing author, same subsystem."""
    dev_experience_state = {'dev1': {'sub1': 3, 'sub2': 1}} # exp=4
    author = 'dev1'
    subsystem = 'sub1'

    result = _update_dev_experience(author, subsystem, dev_experience_state)

    # Check returned historical data
    assert result.exp == 4 # Total exp before update
    assert result.sexp == 3 # Subsystem exp before update
    assert math.isclose(result.rexp, 4.0) # Placeholder REXP = EXP

    # Check state modification
    assert dev_experience_state == {'dev1': {'sub1': 4, 'sub2': 1}}

def test_update_dev_experience_existing_author_new_subsystem():
    """Test dev experience update for existing author, new subsystem."""
    dev_experience_state = {'dev1': {'sub1': 3}} # exp=3
    author = 'dev1'
    subsystem = 'sub2' # New subsystem for this author

    result = _update_dev_experience(author, subsystem, dev_experience_state)

    # Check returned historical data
    assert result.exp == 3
    assert result.sexp == 0 # 0 exp in 'sub2' before update
    assert math.isclose(result.rexp, 3.0)

    # Check state modification
    assert dev_experience_state == {'dev1': {'sub1': 3, 'sub2': 1}}

# --- Tests for Calculation Helpers ---

@pytest.mark.parametrize(
    "loc_modified_per_file, total_loc_modified, expected_entropy",
    [
        ([10, 10, 10], 30, -3 * (1/3 * math.log2(1/3))), # Equal distribution
        ([20, 5, 5], 30, -( (20/30 * math.log2(20/30)) + 2 * (5/30 * math.log2(5/30)) )), # Skewed
        ([30], 30, 0.0), # Single file
        ([], 0, 0.0), # No modifications
        ([10, 0, 5], 15, -( (10/15 * math.log2(10/15)) + (5/15 * math.log2(5/15)) )), # Zero modifications ignored
        ([10, 10], 0, 0.0), # Zero total LOC
    ]
)
def test_calculate_entropy(loc_modified_per_file, total_loc_modified, expected_entropy):
    """Test entropy calculation for various distributions."""
    entropy = _calculate_entropy(loc_modified_per_file, total_loc_modified)
    assert math.isclose(entropy, expected_entropy, abs_tol=1e-9)

def test_finalize_metrics():
    """Test replacement of NaN and Inf."""
    metrics = {
        'a': 1.0,
        'b': np.nan,
        'c': float('inf'),
        'd': float('-inf'),
        'e': None,
        'f': 0
    }
    final_metrics = _finalize_metrics(metrics)
    assert final_metrics == {
        'a': 1.0,
        'b': None,
        'c': None,
        'd': None,
        'e': None,
        'f': 0
    }

# --- Tests for calculate_commit_guru_metrics (Orchestrator) ---

@patch('shared.utils.commit_guru_utils.run_git_command', autospec=True)
def test_calculate_commit_guru_metrics_full_run(mock_run_cmd, tmp_path):
    """Test the main calculation function with sample multi-commit log."""
    mock_run_cmd.return_value = SAMPLE_GIT_LOG_OUTPUT_MULTI
    repo_path = tmp_path # Use temp path for cwd

    results = calculate_commit_guru_metrics(repo_path)

    # Basic checks on structure and count
    assert isinstance(results, list)
    assert len(results) == 2

    # Check first commit results
    commit1 = results[0]
    assert commit1['commit_hash'] == 'c1h'
    assert commit1['author_name'] == 'Author One'
    assert commit1['fix'] is False # 'feat:' message
    assert commit1['files_changed'] == ['src/feature_x.py']
    assert commit1['nf'] == 1.0
    assert commit1['ns'] == 1.0 # 'src' subsystem
    assert commit1['nd'] == 1.0 # 'src' directory
    assert commit1['la'] == 5.0
    assert commit1['ld'] == 2.0
    assert commit1['lt'] == 0.0 # Previous LOC (new file)
    assert commit1['ndev'] == 1.0 # Author One
    assert commit1['age'] == 0.0 # Time diff (new file)
    assert commit1['nuc'] == 0.0 # Previous changes (new file)
    assert commit1['exp'] == 0.0 # Dev exp before this commit
    assert commit1['sexp'] == 0.0 # Subsystem exp before this commit
    assert commit1['rexp'] == 0.0 # REXP before
    assert math.isclose(commit1['entropy'], 0.0) # Only one file

    # Check second commit results
    commit2 = results[1]
    assert commit2['commit_hash'] == 'c2h'
    assert commit2['author_name'] == 'Author Two'
    assert commit2['fix'] is True # 'fix:' message
    assert set(commit2['files_changed']) == {'src/feature_x.py', 'tests/test_feature_x.py'}
    assert commit2['nf'] == 2.0
    assert commit2['ns'] == 2.0 # 'src', 'tests'
    assert commit2['nd'] == 2.0 # 'src', 'tests'
    assert commit2['la'] == 10.0 # 8 + 2
    assert commit2['ld'] == 4.0 # 3 + 1
    # Checks for avg values based on state *before* this commit
    # File 1 ('src/feature_x.py'): previous_loc=3 (5-2), prev_nuc=1, time_diff=3600s, authors={'Author One'}
    # File 2 ('tests/test_feature_x.py'): previous_loc=0, prev_nuc=0, time_diff=0, authors={'Author Two'}
    expected_lt = (3 + 0) / 2.0
    expected_age = ((3600 / 86400.0) + 0) / 2.0
    expected_nuc = (1 + 0) / 2.0
    expected_ndev = 2.0 # {'Author One', 'Author Two'}
    # Dev exp: Author Two is new -> exp=0, sexp=0 for both files before update
    # Author One: exp=1, sexp=0 for 'src/feature_x.py' before update
    expected_exp = (0 + 1) / 2.0
    expected_sexp = (0 + 0) / 2.0
    expected_rexp = (0 + 1) / 2.0
    loc_modified = [8 + 3, 2 + 1] # [11, 3]
    total_loc = 14
    expected_entropy = _calculate_entropy(loc_modified, total_loc)

    assert math.isclose(commit2['lt'], expected_lt)
    assert math.isclose(commit2['age'], expected_age)
    assert math.isclose(commit2['nuc'], expected_nuc)
    assert commit2['ndev'] == expected_ndev
    assert math.isclose(commit2['exp'], expected_exp)
    assert math.isclose(commit2['sexp'], expected_sexp)
    assert math.isclose(commit2['rexp'], expected_rexp)
    assert math.isclose(commit2['entropy'], expected_entropy)


    # Verify git log command call
    expected_cmd = f"git log {commit_guru_utils.COMMIT_GURU_LOG_FORMAT}"
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=repo_path)

@patch('shared.utils.commit_guru_utils.run_git_command', autospec=True)
def test_calculate_commit_guru_metrics_with_since(mock_run_cmd, tmp_path):
    """Test the main calculation function with a since_commit."""
    since_hash = "p0h"
    mock_run_cmd.return_value = SAMPLE_GIT_LOG_OUTPUT_MULTI # Assume log returns commits after p0h
    repo_path = tmp_path

    results = calculate_commit_guru_metrics(repo_path, since_commit=since_hash)

    assert len(results) == 2 # Should still process based on the sample output

    # Verify git log command call with since_commit
    expected_cmd = f"git log {since_hash}..HEAD {commit_guru_utils.COMMIT_GURU_LOG_FORMAT}"
    mock_run_cmd.assert_called_once_with(expected_cmd, cwd=repo_path)

@patch('shared.utils.commit_guru_utils.run_git_command', autospec=True)
def test_calculate_commit_guru_metrics_no_log_output(mock_run_cmd, tmp_path):
    """Test behavior when git log returns empty output."""
    mock_run_cmd.return_value = ""
    repo_path = tmp_path
    results = calculate_commit_guru_metrics(repo_path)
    assert results == []

@patch('shared.utils.commit_guru_utils.run_git_command', autospec=True)
def test_calculate_commit_guru_metrics_log_error_bad_revision(mock_run_cmd, tmp_path):
    """Test behavior when git log fails with bad revision (e.g., empty repo)."""
    since_hash = "nonexistent"
    mock_run_cmd.side_effect = subprocess.CalledProcessError(
        128, cmd="git log", stderr="fatal: bad revision 'nonexistent..HEAD'"
    )
    repo_path = tmp_path
    results = calculate_commit_guru_metrics(repo_path, since_commit=since_hash)
    assert results == [] # Should return empty list gracefully

@patch('shared.utils.commit_guru_utils.run_git_command', autospec=True)
def test_calculate_commit_guru_metrics_log_error_other(mock_run_cmd, tmp_path):
    """Test behavior when git log fails with another error."""
    mock_run_cmd.side_effect = subprocess.CalledProcessError(
        1, cmd="git log", stderr="Some other git error"
    )
    repo_path = tmp_path
    with pytest.raises(subprocess.CalledProcessError):
        calculate_commit_guru_metrics(repo_path)


# --- Tests for GitCommitLinker ---

class TestGitCommitLinker:

    @pytest.fixture
    def linker(self, tmp_path):
        """Fixture to create a GitCommitLinker instance with a valid path."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        return GitCommitLinker(repo_path)

    @pytest.fixture(autouse=True)
    def patch_linker_deps(self):
        """Patch dependencies for all GitCommitLinker tests."""
        with patch('shared.utils.commit_guru_utils.run_git_command', autospec=True) as mock_run, \
             patch('shared.utils.commit_guru_utils.find_commit_hash_before_timestamp', autospec=True) as mock_find:
            yield mock_run, mock_find

    def test_linker_init_success(self, tmp_path):
        """Test successful initialization."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        linker = GitCommitLinker(repo_path)
        assert linker.repo_path == repo_path

    def test_linker_init_path_not_found(self, tmp_path):
        """Test initialization failure if path doesn't exist."""
        repo_path = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            GitCommitLinker(repo_path)

    def test_get_modified_regions(self, linker, patch_linker_deps):
        """Test _get_modified_regions parsing."""
        mock_run_cmd, _ = patch_linker_deps
        # Simulate git diff and git diff --name-only calls
        mock_run_cmd.side_effect = [
            SAMPLE_DIFF_U0,      # Output for 'git diff -U0 ...'
            SAMPLE_NAME_ONLY     # Output for 'git diff --name-only ...'
        ]
        # Assume CODE_FILE_EXTENSIONS includes 'py' but not 'md'
        commit_guru_utils.CODE_FILE_EXTENSIONS = {'PY'} # Override for test

        regions = linker._get_modified_regions("dummy_hash")

        assert 'src/main.py' in regions
        assert regions['src/main.py'] == [10] # Only line 10 was deleted (-)
        assert 'README.md' not in regions # Should be skipped as not in CODE_FILE_EXTENSIONS

        assert mock_run_cmd.call_count == 2
        assert 'git diff -U0 dummy_hash^ dummy_hash' in mock_run_cmd.call_args_list[0].args[0]
        assert 'git diff --name-only dummy_hash^ dummy_hash' in mock_run_cmd.call_args_list[1].args[0]

    def test_get_modified_regions_initial_commit_error(self, linker, patch_linker_deps):
        """Test handling initial commit error during diff."""
        mock_run_cmd, _ = patch_linker_deps
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "git diff", stderr="unknown revision")

        regions = linker._get_modified_regions("initial_hash")
        assert regions == {}
        assert mock_run_cmd.call_count == 1 # Only first diff command fails

    def test_get_modified_regions_other_error(self, linker, patch_linker_deps):
        """Test handling other errors during diff."""
        mock_run_cmd, _ = patch_linker_deps
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "git diff", stderr="some other error")

        regions = linker._get_modified_regions("some_hash")
        assert regions == {}
        assert mock_run_cmd.call_count == 1


    def test_git_annotate_regions_simple_success(self, linker, patch_linker_deps):
        """Test _git_annotate_regions finding introducing commits."""
        mock_run_cmd, mock_find_commit = patch_linker_deps
        mock_run_cmd.return_value = SAMPLE_BLAME_OUTPUT
        mock_find_commit.return_value = None # No timestamp provided/found

        regions = {'src/main.py': [10, 16]}
        corrective_hash = "c0rrect1v3"
        start_commit = f"{corrective_hash}^"

        introducing = linker._git_annotate_regions(regions, corrective_hash, None)

        assert introducing == {'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'f0e1d2c3b4a5f0e1d2c3b4a5f0e1d2c3b4a5f0e1'}
        mock_run_cmd.assert_called_once()
        blame_cmd_arg = mock_run_cmd.call_args.args[0]
        assert f"git blame --porcelain -w {start_commit}" in blame_cmd_arg
        assert "-L 10,10" in blame_cmd_arg
        assert "-L 16,16" in blame_cmd_arg
        assert '-- "src/main.py"' in blame_cmd_arg
        mock_find_commit.assert_not_called()

    def test_git_annotate_regions_with_timestamp_and_fallback(self, linker, patch_linker_deps):
        """Test blame fallback when timestamp-based commit fails."""
        mock_run_cmd, mock_find_commit = patch_linker_deps
        corrective_hash = "c0rrect1v3"
        start_commit_ts = "ts_commit_hash"
        start_commit_parent = f"{corrective_hash}^"
        timestamp = 1705000000

        # 1. find_commit returns a hash
        mock_find_commit.return_value = start_commit_ts
        # 2. First blame call (from ts_commit) fails with "no such path"
        # 3. Second blame call (from parent) succeeds
        mock_run_cmd.side_effect = [
            subprocess.CalledProcessError(1, "git blame", stderr="fatal: no such path 'src/main.py' in ts_commit_hash"),
            SAMPLE_BLAME_OUTPUT # Success on fallback
        ]

        regions = {'src/main.py': [10]}
        introducing = linker._git_annotate_regions(regions, corrective_hash, timestamp)

        # Assert based on the hashes present in SAMPLE_BLAME_OUTPUT provided by the mock
        assert introducing == {'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'f0e1d2c3b4a5f0e1d2c3b4a5f0e1d2c3b4a5f0e1'}
        mock_find_commit.assert_called_once_with(linker.repo_path, timestamp)
        assert mock_run_cmd.call_count == 2
        # Check first call args
        blame_cmd_arg1 = mock_run_cmd.call_args_list[0].args[0]
        assert f"git blame --porcelain -w {start_commit_ts}" in blame_cmd_arg1
        # Check second call args
        blame_cmd_arg2 = mock_run_cmd.call_args_list[1].args[0]
        assert f"git blame --porcelain -w {start_commit_parent}" in blame_cmd_arg2


    def test_git_annotate_regions_excludes_self_and_start(self, linker, patch_linker_deps):
        """Test that blame excludes corrective commit and start commit."""
        mock_run_cmd, mock_find_commit = patch_linker_deps
        corrective_hash = "c0rrect1v3"
        start_commit = f"{corrective_hash}^" # Assume this hash is 'p4r3nt_h4sh'
        # Modify blame output to include corrective and start hash
        blame_output_with_self = f"""
{corrective_hash} 10 10 1
author Corrective Author
...
\t line from corrective
p4r3nt_h4sh 16 16 1
author Parent Author
...
\t line from parent
f0e1d2c3b4a5f0e1d2c3b4a5f0e1d2c3b4a5f0e1 18 18 1
author Other Author
...
\t line from other commit
"""
        mock_run_cmd.return_value = blame_output_with_self
        mock_find_commit.return_value = None

        regions = {'src/main.py': [10, 16, 18]}
        introducing = linker._git_annotate_regions(regions, corrective_hash, None)

        # Should only contain the 'other' commit hash
        assert introducing == {'f0e1d2c3b4a5f0e1d2c3b4a5f0e1d2c3b4a5f0e1'}

    
    def test_link_corrective_commits(self, linker, patch_linker_deps):
        """Test the main orchestration method of GitCommitLinker using explicit mock mapping."""
        mock_run_cmd, mock_find_commit = patch_linker_deps
        mock_find_commit.return_value = None # Assume no timestamps for simplicity here

        # --- Define expected behavior with explicit mapping ---
        regions_map = {
            "corrective1": {'file1.py': [5, 10]},
            "corrective2": {},
            "corrective3": {'file2.py': [20]},
        }
        annotation_map = {
            # corrective_hash -> set_of_buggy_hashes
            "corrective1": {'buggy1', 'buggy2'},
            # No entry for corrective2 as it has no regions
            "corrective3": {'buggy2'},
        }

        def mock_get_regions_side_effect(commit_hash: str):
            print(f"\nDEBUG (Mock): _get_modified_regions called with: {commit_hash}")
            return regions_map.get(commit_hash, {}) # Return {} if hash not found

        def mock_annotate_side_effect(regions: Dict, commit_hash: str, timestamp: Optional[int]):
            print(f"\nDEBUG (Mock): _git_annotate_regions called with commit: {commit_hash}, regions: {regions}")
            # Find the result based on the corrective_hash passed to this mock
            return annotation_map.get(commit_hash, set()) # Return empty set if not found


        # Mock internal methods using functions for side_effect
        with patch.object(linker, '_get_modified_regions', side_effect=mock_get_regions_side_effect, autospec=True) as mock_regions_method, \
            patch.object(linker, '_git_annotate_regions', side_effect=mock_annotate_side_effect, autospec=True) as mock_annotate_method:

            corrective_info = {
                "corrective1": None,
                "corrective2": None,
                "corrective3": None,
            }

            bug_link_map = linker.link_corrective_commits(corrective_info)


            # Assertions
            assert 'buggy1' in bug_link_map
            assert bug_link_map['buggy1'] == ['corrective1']

            assert 'buggy2' in bug_link_map
            # order is random xDDDD
            #assert bug_link_map['buggy2'] == ['corrective1', 'corrective3']
            # Assert using set as well for robustness against potential order changes
            assert set(bug_link_map['buggy2']) == {'corrective1', 'corrective3'}

            # Check calls to mocks
            # Should be called for corrective1, corrective2, corrective3
            assert mock_regions_method.call_count == 3
            # Should be called for corrective1 and corrective3 (corrective2 had no regions)
            assert mock_annotate_method.call_count == 2
            # You can add more detailed call_args checks if needed