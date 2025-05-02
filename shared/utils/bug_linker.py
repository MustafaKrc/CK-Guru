# shared/utils/bug_linker.py
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Mapping, Set, Any, Optional, Tuple

from shared.core.config import settings
# Assuming git_utils is in the same directory or accessible
from shared.utils.git_utils import run_git_command, find_commit_hash_before_timestamp

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Constants for bug linking
CODE_FILE_EXTENSIONS = { # Keep code extensions relevant to linking
    'ADA', 'ADB', 'ADS', 'ASM', 'BAS', 'BB', 'BMX', 'C', 'CLJ', 'CLS',
    'COB', 'CBL', 'CPP', 'CC', 'CXX', 'CBP', 'CS', 'CSPROJ', 'D', 'DBA',
    'DBPro123', 'E', 'EFS', 'EGT', 'EL', 'FOR', 'FTN', 'F', 'F77', 'F90',
    'FRM', 'GO', 'H', 'HPP', 'HXX', 'HS', 'I', 'INC', 'JAVA', 'L', 'LGT',
    'LISP', 'M', 'M4', 'ML', 'N', 'NB', 'P', 'PAS', 'PP', 'PHP', 'PHP3',
    'PHP4', 'PHP5', 'PHPS', 'Phtml', 'PIV', 'PL', 'PM', 'PRG', 'PRO', 'PY',
    'R', 'RB', 'RESX', 'RC', 'RC2', 'RKT', 'RKTL', 'SCI', 'SCE', 'SCM',
    'SD7', 'SKB', 'SKC', 'SKD', 'SKF', 'SKG', 'SKI', 'SKK', 'SKM', 'SKO',
    'SKP', 'SKQ', 'SKS', 'SKT', 'SKZ', 'SLN', 'SPIN', 'STK', 'SWG', 'TCL',
    'VAP', 'VB', 'VBG', 'XPL', 'XQ', 'XSL', 'Y', 'AHK', 'APPLESCRIPT', 'AS',
    'AU3', 'BAT', 'CMD', 'COFFEE', 'EGG', 'ERB', 'HTA', 'IBI', 'ICI', 'IJS',
    'ITCL', 'JS', 'JSFL', 'LUA', 'MRC', 'NCF', 'NUT', 'PS1', 'PS1XML', 'PSC1',
    'PSD1', 'PSM1', 'RDP', 'SCPT', 'SCPTD', 'SDL', 'SH', 'VBS', 'EBUILD'
}

class GitCommitLinker:
    """
    Links corrective changes/commits from a git repository
    to changes that introduced the problem using git blame.
    """
    _HUNK_HEADER_REGEX = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    _DIFF_GIT_HEADER_REGEX = re.compile(r'diff --git a/(.*?) b/(.*)')

    def __init__(self, repo_path: Path):
        """
        Constructor. Sets the repository path.
        """
        if not repo_path or not repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist or is not a directory: {repo_path}")
        self.repo_path: Path = repo_path
        logger.info(f"GitCommitLinker initialized for repository: {self.repo_path}")

    def link_corrective_commits(
        self,
        corrective_commits_info: Mapping[str, Optional[int]] # Hash -> Earliest Issue Timestamp
    ) -> Dict[str, List[str]]:
        """
        Links corrective commits to the commits that likely introduced the bug.
        Uses earliest issue timestamp to refine blame starting point if available.

        Args:
            corrective_commits_info: Mapping of corrective commit hash to its optional
                                     earliest linked issue timestamp.

        Returns:
            A dictionary where keys are the hashes of *buggy* (introducing) commits
            and values are lists of *corrective* commit hashes that fixed them.
        """
        bug_link_map: Dict[str, List[str]] = {} # buggy_hash -> [fixing_hash1, fixing_hash2,...]
        total_corrective = len(corrective_commits_info)
        processed_count = 0

        logger.info(f"BugLinker: Starting bug linking for {total_corrective} corrective commits...")

        corrective_commit_hashes = set(corrective_commits_info.keys())

        for corrective_hash in corrective_commit_hashes:
            processed_count += 1
            earliest_issue_ts = corrective_commits_info.get(corrective_hash) # Get timestamp

            if processed_count % 10 == 0 or processed_count == total_corrective:
                ts_info = f"(IssueTS: {earliest_issue_ts})" if earliest_issue_ts else "(No IssueTS)"
                logger.info(f"BugLinker: Linking {processed_count}/{total_corrective}: {corrective_hash[:7]} {ts_info}...")

            try:
                modified_regions = self._get_modified_regions(corrective_hash)
                if not modified_regions:
                    logger.debug(f"BugLinker: No code regions found for {corrective_hash[:7]}.")
                    continue

                introducing_commits = self._git_annotate_regions(
                    modified_regions, corrective_hash, earliest_issue_ts
                )

                for buggy_hash in introducing_commits:
                    # Ensure the identified "buggy" commit isn't itself corrective (unlikely but possible)
                    # if buggy_hash not in corrective_commit_hashes: # Optional check
                    if buggy_hash not in bug_link_map:
                        bug_link_map[buggy_hash] = []
                    # Avoid adding the same fix multiple times if blame points to it multiple times
                    if corrective_hash not in bug_link_map[buggy_hash]:
                         bug_link_map[buggy_hash].append(corrective_hash)

            except Exception as e:
                logger.error(f"BugLinker: Error linking {corrective_hash[:7]}: {e}", exc_info=True)

        linked_count = len(bug_link_map)
        logger.info(f"BugLinker: Finished. Identified {linked_count} potential bug-introducing commits from {total_corrective} corrective commits.")
        if logger.isEnabledFor(logging.DEBUG) and bug_link_map:
            debug_map_str = json.dumps({k[:7]: [v[:7] for v in vals] for k, vals in list(bug_link_map.items())[:5]}, indent=2)
            logger.debug(f"BugLinker: Sample map (buggy -> [fixing]):\n{debug_map_str}")

        return bug_link_map

    def _get_modified_regions(self, commit_hash: str) -> Dict[str, List[int]]:
        """
        Gets files and line numbers modified/deleted in a commit compared to its first parent.
        Focuses only on code files based on CODE_FILE_EXTENSIONS.
        """
        # Use ^1 explicitly to target the first parent, common for non-merge fixes
        diff_cmd = f"git diff -U0 {commit_hash}^1 {commit_hash}"
        files_cmd = f"git diff --name-only {commit_hash}^1 {commit_hash}"
        modified_regions: Dict[str, List[int]] = {}

        try:
            # Check if the commit has a parent first
            parent_check_cmd = f"git rev-parse --verify {commit_hash}^1"
            run_git_command(parent_check_cmd, cwd=self.repo_path) # Throws error if no parent

            diff_output = run_git_command(diff_cmd, cwd=self.repo_path)
            files_modified_output = run_git_command(files_cmd, cwd=self.repo_path)
            files_modified = set(fn.strip() for fn in files_modified_output.splitlines() if fn.strip())

            modified_regions = self._parse_diff_for_modified_lines(diff_output, files_modified)

        except subprocess.CalledProcessError as e:
            err_lower = e.stderr.lower().strip()
            # Handle common cases gracefully (no parent, unknown revision)
            if "unknown revision" in err_lower or "bad revision" in err_lower or "no merge base" in err_lower:
                logger.warning(f"BugLinker: Could not get diff for {commit_hash[:7]} (likely initial commit or merge issue): {err_lower}")
            else:
                logger.error(f"BugLinker: Error getting git diff for {commit_hash[:7]}: {err_lower}")
            return {} # Return empty on error
        except Exception as e:
            logger.error(f"BugLinker: Unexpected error getting diff/files for {commit_hash[:7]}: {e}", exc_info=True)
            return {}

        return modified_regions


    def _parse_diff_for_modified_lines(self, diff_output: str, files_modified: Set[str]) -> Dict[str, List[int]]:
        """Parses `git diff -U0` output for modified/deleted line numbers in known code files."""
        modified_lines_map: Dict[str, List[int]] = {}
        current_file: Optional[str] = None
        lines = diff_output.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]; i += 1
            if line.startswith('diff --git'):
                match = self._DIFF_GIT_HEADER_REGEX.match(line)
                if match:
                    # Use file path from 'a/' side for blaming parent state
                    potential_file = match.group(1).strip()
                    if potential_file in files_modified:
                        file_ext_parts = potential_file.rsplit('.', 1) # Split only once from right
                        if len(file_ext_parts) > 1 and file_ext_parts[-1].upper() in CODE_FILE_EXTENSIONS:
                            current_file = potential_file
                            if current_file not in modified_lines_map: modified_lines_map[current_file] = []
                        else: current_file = None # Skip non-code files
                    else: current_file = None
                else: current_file = None
            elif line.startswith('@@') and current_file:
                hunk_match = self._HUNK_HEADER_REGEX.match(line)
                if hunk_match:
                    current_line_num_old = int(hunk_match.group(1))
                    while i < len(lines) and not lines[i].startswith(('diff --git', '@@ ')):
                        hunk_line = lines[i]; i += 1
                        if hunk_line.startswith('-') and not hunk_line.startswith('---'):
                            modified_lines_map[current_file].append(current_line_num_old)
                            current_line_num_old += 1
                        elif hunk_line.startswith('+') and not hunk_line.startswith('+++'): pass # Ignore added lines
                        else: # Context line (ignore with -U0) or other lines
                            if not hunk_line.startswith('+'): current_line_num_old += 1 # Increment only if not added
                else: logger.warning(f"BugLinker: Could not parse hunk header: {line} in file {current_file}")

        return {f: lines for f, lines in modified_lines_map.items() if lines}

    def _git_annotate_regions(
        self,
        regions: Dict[str, List[int]],
        corrective_commit_hash: str,
        earliest_issue_timestamp: Optional[int]
    ) -> Set[str]:
        """Uses `git blame` to find the origins of modified lines, with fallback."""
        introducing_commits: Set[str] = set()
        default_blame_start = f"{corrective_commit_hash}^1" # Blame state before the fix commit (first parent)
        initial_blame_start_commit: Optional[str] = default_blame_start
        used_issue_timestamp = False

        # --- Determine Blame Start Commit ---
        if earliest_issue_timestamp:
            logger.debug(f"BugLinker: Using issue timestamp {earliest_issue_timestamp} for {corrective_commit_hash[:7]}")
            commit_before_issue = find_commit_hash_before_timestamp(self.repo_path, earliest_issue_timestamp)
            if commit_before_issue:
                initial_blame_start_commit = commit_before_issue
                used_issue_timestamp = True
                logger.debug(f"BugLinker: Initial blame start: {initial_blame_start_commit[:7]} (from timestamp)")
            else:
                logger.warning(f"BugLinker: Could not find commit before timestamp {earliest_issue_timestamp}. Using parent {default_blame_start[:7]}.")
                initial_blame_start_commit = default_blame_start
        else:
            logger.debug(f"BugLinker: Initial blame start: {default_blame_start[:7]} (parent)")
        # --- End Determine Blame Start ---

        if not initial_blame_start_commit:
             logger.error(f"BugLinker: Could not determine blame start for {corrective_commit_hash[:7]}. Skipping blame.")
             return introducing_commits

        for file_path, line_numbers in regions.items():
            if not line_numbers: continue
            blame_succeeded = False
            blame_output = ""
            current_blame_start = initial_blame_start_commit

            # --- Attempt Blame (Initial or Fallback) ---
            for attempt in range(2): # Max 2 attempts (initial, then fallback)
                if attempt == 1 and not used_issue_timestamp: break # No fallback if initial was already parent
                if attempt == 1: # If it's the fallback attempt
                    current_blame_start = default_blame_start
                    logger.warning(f"BugLinker: Falling back to blame from parent {current_blame_start[:7]} for '{file_path}'")

                logger.debug(f"BugLinker: Blaming {file_path} L{line_numbers[0]}-{line_numbers[-1]} from {current_blame_start[:7]}")
                line_args = " ".join([f"-L {ln},{ln}" for ln in line_numbers])
                # Use -- C essential if file paths might start with -
                # -w: ignore whitespace changes
                blame_cmd = f"git blame --porcelain -w {current_blame_start} {line_args} -- \"{file_path}\""

                try:
                    blame_output = run_git_command(blame_cmd, cwd=self.repo_path)
                    blame_succeeded = True
                    break # Success, exit attempt loop
                except subprocess.CalledProcessError as e:
                    stderr_lower = e.stderr.lower()
                    if "fatal: no such path" in stderr_lower and attempt == 0 and used_issue_timestamp:
                        logger.warning(f"BugLinker: Blame from {current_blame_start[:7]} failed for '{file_path}' (no path). Will try fallback.")
                        continue # Go to next attempt (fallback)
                    elif "bad revision" in stderr_lower:
                        logger.warning(f"BugLinker: Blame failed for '{file_path}' at {current_blame_start[:7]} (bad revision): {e.stderr.strip()}")
                    else:
                        logger.warning(f"BugLinker: Blame failed for '{file_path}' at {current_blame_start[:7]}: {e.stderr.strip()}")
                    break # Error other than 'no path' on first attempt, or any error on fallback: stop trying for this file
                except Exception as e:
                    logger.error(f"BugLinker: Unexpected error running blame for {file_path} at {current_blame_start[:7]}: {e}", exc_info=True)
                    break # Stop trying on unexpected errors

            # --- Process Blame Output ---
            if blame_succeeded and blame_output:
                try:
                    blame_hashes_in_output = set()
                    for line in blame_output.strip().splitlines():
                        parts = line.split()
                        if len(parts) > 0 and len(parts[0]) == 40 and all(c in '0123456789abcdef' for c in parts[0]):
                            potential_hash = parts[0]
                            # Add if it's not the fix commit itself or the commit we blamed *from*
                            if potential_hash != corrective_commit_hash and potential_hash != current_blame_start:
                                blame_hashes_in_output.add(potential_hash)
                    introducing_commits.update(blame_hashes_in_output)
                except Exception as parse_err:
                    logger.error(f"BugLinker: Error parsing blame output for {file_path} (start: {current_blame_start[:7]}): {parse_err}", exc_info=True)

        return introducing_commits