# worker/app/tasks/utils/commit_guru_utils.py
import re
import json
import math
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Mapping, Set, Any, Optional, Tuple, NamedTuple

from .git_utils import find_commit_hash_before_timestamp, run_git_command

logger = logging.getLogger(__name__)

# --- Constants ---
# (CODE_FILE_EXTENSIONS, CORRECTIVE_KEYWORDS, COMMIT_GURU_LOG_FORMAT)
CODE_FILE_EXTENSIONS = {
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
CORRECTIVE_KEYWORDS = {'fix', 'bug', 'defect', 'error', 'patch'}
COMMIT_GURU_LOG_FORMAT = (
    '--pretty=format:\"<CAS_COMMIT_START>'
    '<CAS_FIELD>parent_hashes<CAS_DELIM>%P<CAS_END>'
    '<CAS_FIELD>commit_hash<CAS_DELIM>%H<CAS_END>'
    '<CAS_FIELD>author_name<CAS_DELIM>%an<CAS_END>'
    '<CAS_FIELD>author_email<CAS_DELIM>%ae<CAS_END>'
    '<CAS_FIELD>author_date<CAS_DELIM>%ad<CAS_END>'
    '<CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>%at<CAS_END>'
    # %B includes subject and body, %n adds newline between them if multiline
    '<CAS_FIELD>commit_message<CAS_DELIM>%B%n<CAS_END>'
    '<CAS_COMMIT_END>\" --numstat --reverse --encoding=UTF-8'
    # Consider adding --no-merges if merge commits without stats are problematic
    # '--no-merges'
)
# --- End Constants ---

# --- Data Structures ---
class CommitFile:
    """Represents a file tracked across commits for metric calculation."""
    def __init__(self, name: str, loc: int, authors: List[str], lastchanged: int):
        self.name: str = name
        self.loc: int = loc
        self.authors: List[str] = authors
        self.lastchanged: int = lastchanged
        self.nuc: int = 1

    def __repr__(self):
        return f"<CommitFile(name='{self.name}', loc={self.loc}, lastchanged={self.lastchanged}, nuc={self.nuc})>"

class ParsedNumstatLine(NamedTuple):
    """Structured data from a parsed --numstat line."""
    la: int
    ld: int
    file_name: str
    subsystem: str
    directory: str

class FileUpdateResult(NamedTuple):
    """Result of updating file state for a single file in a commit."""
    previous_loc: int
    previous_nuc: int
    time_diff_days: float
    authors_involved: Set[str]

class DevExperienceMetrics(NamedTuple):
    """Developer experience metrics calculated for a file interaction."""
    exp: int  # Total experience of the author *before* this commit
    rexp: float # Weighted experience (placeholder)
    sexp: int  # Subsystem experience of the author *before* this commit in this subsystem
# --- End Data Structures ---


# --- Helper Functions ---

def _parse_commit_guru_log(log_output: str) -> List[Dict[str, Any]]:
    """Parses the custom formatted git log output."""
    commits_data = []
    commit_blobs = log_output.strip().split('<CAS_COMMIT_START>')[1:]

    if not commit_blobs:
        logger.warning("No commit blobs found in log output.")
        return []

    commit_regex = re.compile(r"(.*?)<CAS_COMMIT_END>(.*)", re.DOTALL)
    field_regex = re.compile(r"<CAS_FIELD>(.*?)<CAS_DELIM>(.*?)<CAS_END>", re.DOTALL)

    for blob in commit_blobs:
        match = commit_regex.match(blob)
        if not match:
            logger.warning(f"Could not parse commit blob: {blob[:100]}...")
            continue

        pretty_part = match.group(1)
        stats_part = match.group(2).strip()
        commit_info = {}

        for field_match in field_regex.finditer(pretty_part):
            key = field_match.group(1).strip()
            # Remove potential trailing newline from commit message
            value = field_match.group(2).strip()
            commit_info[key] = value

        if 'commit_hash' not in commit_info:
            logger.warning(f"Parsed commit blob missing commit_hash: {pretty_part}")
            continue

        commit_info['stats_lines'] = stats_part.splitlines()
        commits_data.append(commit_info)

    logger.info(f"Parsed {len(commits_data)} commits from log output.")
    return commits_data

def _parse_numstat_line(line: str, commit_hash_debug: str) -> Optional[ParsedNumstatLine]:
    """Parses a single --numstat line, returning structured data or None."""
    if not line.strip():
        return None

    parts = line.split('\t')
    if len(parts) != 3:
        logger.warning(f"Skipping malformed stats line: '{line}' in commit {commit_hash_debug}")
        return None

    la_str, ld_str, file_path = parts

    try:
        # *** APPLYING THE FIX HERE ***
        # Convert to int immediately after parsing
        file_la = 0 if la_str == '-' else int(la_str)
        file_ld = 0 if ld_str == '-' else int(ld_str)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse LA/LD '{la_str}/{ld_str}' for file '{file_path}' in commit {commit_hash_debug}. Skipping file.")
        return None

    file_name = file_path.strip().replace("'", "").replace('"', '')
    if not file_name:
        return None

    file_parts = file_name.split('/')
    subsystem = file_parts[0] if len(file_parts) > 1 else "root"
    directory = "/".join(file_parts[:-1]) if len(file_parts) > 1 else "root"

    return ParsedNumstatLine(file_la, file_ld, file_name, subsystem, directory)

def _update_file_state(
    parsed_line: ParsedNumstatLine,
    author: str,
    timestamp: int,
    commit_files_state: Dict[str, CommitFile]
) -> FileUpdateResult:
    """
    Updates the state for a single file based on a commit.
    Modifies commit_files_state IN PLACE.
    Returns metrics derived from the file's history *before* this update.
    """
    file_name = parsed_line.file_name
    file_la = parsed_line.la
    file_ld = parsed_line.ld

    previous_loc = 0
    previous_nuc = 0
    time_diff_days = 0.0
    authors_involved: Set[str] = set()

    if file_name in commit_files_state:
        file_state = commit_files_state[file_name]
        previous_loc = file_state.loc
        previous_nuc = file_state.nuc
        time_diff_seconds = timestamp - file_state.lastchanged
        time_diff_days = max(0, time_diff_seconds) / 86400.0
        authors_involved.update(file_state.authors) # Authors who touched it before

        # Update state
        file_state.loc += (file_la - file_ld)
        file_state.authors = list(set(file_state.authors + [author]))
        file_state.lastchanged = timestamp
        file_state.nuc += 1
    else:
        # New file state
        authors_involved.add(author)
        commit_files_state[file_name] = CommitFile(
            name=file_name,
            loc=(file_la - file_ld),
            authors=[author],
            lastchanged=timestamp
        )

    return FileUpdateResult(previous_loc, previous_nuc, time_diff_days, authors_involved)

def _update_dev_experience(
    author: str,
    subsystem: str,
    dev_experience_state: Dict[str, Dict[str, int]]
) -> DevExperienceMetrics:
    """
    Updates developer experience state.
    Modifies dev_experience_state IN PLACE.
    Returns experience metrics *before* this update.
    """
    exp = 0
    sexp = 0
    rexp = 0.0 # Placeholder - REXP needs clarification

    if author in dev_experience_state:
        author_exp_map = dev_experience_state[author]
        exp = sum(author_exp_map.values()) # Total exp before this commit
        sexp = author_exp_map.get(subsystem, 0) # Subsystem exp before this commit
        rexp = float(exp) # Placeholder approximation for REXP

        # Update experience *after* calculating metrics for this commit
        author_exp_map[subsystem] = author_exp_map.get(subsystem, 0) + 1
    else:
        # First commit for this author - exp, sexp, rexp are 0
        # Initialize state *after* calculating metrics
        dev_experience_state[author] = {subsystem: 1}

    return DevExperienceMetrics(exp, rexp, sexp)

def _calculate_entropy(loc_modified_per_file: List[int], total_loc_modified: int) -> float:
    """Calculates code churn entropy."""
    entropy = 0.0
    if total_loc_modified > 0:
        for mod_loc in loc_modified_per_file:
            if mod_loc > 0:
                proportion = mod_loc / total_loc_modified
                try:
                    if proportion > 1e-9: # Avoid log2(0)
                       entropy -= proportion * math.log2(proportion)
                except ValueError:
                     logger.warning(f"ValueError during entropy calculation for proportion {proportion}. Skipping term.")
    return entropy

def _finalize_metrics(metrics: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Replaces NaN/Inf with None."""
    final_metrics = {}
    for key, value in metrics.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            final_metrics[key] = None
        else:
            final_metrics[key] = value
    return final_metrics
# --- End Helper Functions ---


# --- Main Calculation Function ---
def calculate_commit_guru_metrics(repo_path: Path, since_commit: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Calculates Commit Guru metrics for a repository by processing git log output.

    Args:
        repo_path: Path to the locally cloned git repository.
        since_commit: Optional commit hash. If provided, analyze commits after this.

    Returns:
        A list of dictionaries, each representing a commit with its calculated metrics.
    """
    logger.info(f"Calculating Commit Guru metrics for repository at {repo_path}")
    cmd = f"git log {COMMIT_GURU_LOG_FORMAT}"
    if since_commit:
        cmd = f"git log {since_commit}..HEAD {COMMIT_GURU_LOG_FORMAT}"
        logger.info(f"Analyzing commits since {since_commit}")
    else:
        logger.info("Analyzing all commits.")

    try:
        log_output = run_git_command(cmd, cwd=repo_path)
    except subprocess.CalledProcessError as e:
        if "fatal: bad revision" not in e.stderr and "unknown revision" not in e.stderr:
             raise
        else:
             logger.info(f"No new commits found since {since_commit} or repository is empty.")
             log_output = ""
    except Exception:
        raise # Re-raise other unexpected errors

    if not log_output:
        logger.info("Git log output is empty. No metrics to calculate.")
        return []

    parsed_commits = _parse_commit_guru_log(log_output)
    if not parsed_commits:
        logger.warning("Parsing git log yielded no commit data.")
        return []

    # Initialize state that persists across commits
    commit_files_state: Dict[str, CommitFile] = {}
    dev_experience_state: Dict[str, Dict[str, int]] = {}
    results: List[Dict[str, Any]] = []

    logger.info(f"Calculating metrics for {len(parsed_commits)} commits...")
    for i, commit_data in enumerate(parsed_commits):
        commit_hash = commit_data.get('commit_hash', 'UNKNOWN')
        author = commit_data.get('author_name', 'Unknown')
        try:
             timestamp = int(commit_data.get('author_date_unix_timestamp', '0'))
        except (ValueError, TypeError):
             timestamp = 0

        # Accumulators for this specific commit
        commit_metrics: Dict[str, Optional[float]] = {
            'ns': 0.0, 'nd': 0.0, 'nf': 0.0, 'entropy': 0.0, 'la': 0.0,
            'ld': 0.0, 'lt': 0.0, 'ndev': 0.0, 'age': 0.0, 'nuc': 0.0,
            'exp': 0.0, 'rexp': 0.0, 'sexp': 0.0
        }
        total_lt = 0.0
        total_nuc = 0
        total_age_days = 0.0
        total_exp = 0
        total_rexp = 0.0
        total_sexp = 0
        total_loc_modified = 0
        files_changed_count = 0
        authors_in_commit: Set[str] = set()
        subsystems_in_commit: Set[str] = set()
        directories_in_commit: Set[str] = set()
        loc_modified_per_file: List[int] = []
        files_seen_paths: List[str] = []

        # Process each file change reported by numstat for this commit
        for line in commit_data.get('stats_lines', []):
            parsed_line = _parse_numstat_line(line, commit_hash[:7])
            if not parsed_line:
                continue

            files_changed_count += 1
            files_seen_paths.append(parsed_line.file_name)
            subsystems_in_commit.add(parsed_line.subsystem)
            directories_in_commit.add(parsed_line.directory)

            # Update states and get historical data for this file
            file_update_result = _update_file_state(
                parsed_line, author, timestamp, commit_files_state
            )
            dev_exp_result = _update_dev_experience(
                author, parsed_line.subsystem, dev_experience_state
            )

            # Accumulate commit-level totals
            commit_metrics['la'] += parsed_line.la # Direct accumulation of int
            commit_metrics['ld'] += parsed_line.ld # Direct accumulation of int
            loc_in_file = parsed_line.la + parsed_line.ld
            loc_modified_per_file.append(loc_in_file)
            total_loc_modified += loc_in_file

            total_lt += file_update_result.previous_loc
            total_nuc += file_update_result.previous_nuc
            total_age_days += file_update_result.time_diff_days
            authors_in_commit.update(file_update_result.authors_involved)

            total_exp += dev_exp_result.exp
            total_rexp += dev_exp_result.rexp
            total_sexp += dev_exp_result.sexp

        # Calculate final metrics for the commit
        if files_changed_count > 0:
            commit_metrics['nf'] = float(files_changed_count)
            commit_metrics['ns'] = float(len(subsystems_in_commit))
            commit_metrics['nd'] = float(len(directories_in_commit))
            commit_metrics['ndev'] = float(len(authors_in_commit))
            commit_metrics['entropy'] = _calculate_entropy(loc_modified_per_file, total_loc_modified)

            # Calculate averages
            commit_metrics['lt'] = total_lt / files_changed_count
            commit_metrics['age'] = total_age_days / files_changed_count
            commit_metrics['nuc'] = total_nuc / files_changed_count
            commit_metrics['exp'] = total_exp / files_changed_count
            commit_metrics['rexp'] = total_rexp / files_changed_count
            commit_metrics['sexp'] = total_sexp / files_changed_count
        else:
            # If no files changed (e.g., empty commit), metrics remain 0
             commit_metrics['nf'] = 0.0
             commit_metrics['ns'] = 0.0
             commit_metrics['nd'] = 0.0
             commit_metrics['ndev'] = 0.0
             commit_metrics['entropy'] = 0.0
             commit_metrics['lt'] = 0.0
             commit_metrics['age'] = 0.0
             commit_metrics['nuc'] = 0.0
             commit_metrics['exp'] = 0.0
             commit_metrics['rexp'] = 0.0
             commit_metrics['sexp'] = 0.0


        # Prepare final data payload for this commit
        final_data = commit_data.copy()
        final_data.pop('stats_lines', None) # Remove raw stats lines
        final_data.update(_finalize_metrics(commit_metrics)) # Add calculated metrics (NaN/Inf handled)
        final_data['files_changed'] = files_seen_paths if files_seen_paths else None

        # Add simple 'fix' keyword flag
        commit_message = final_data.get('commit_message', '').lower()
        final_data['fix'] = any(word in commit_message for word in CORRECTIVE_KEYWORDS)

        # Ensure timestamp is integer
        final_data['author_date_unix_timestamp'] = timestamp

        results.append(final_data)

        if (i + 1) % 500 == 0:
            logger.info(f"Calculated metrics for {i + 1}/{len(parsed_commits)} commits...")

    logger.info(f"Finished calculating Commit Guru metrics for {len(results)} commits.")
    return results
# --- End Main Calculation Function ---


# ==================================================
#           GitCommitLinker Adaptation
# ==================================================
class GitCommitLinker:
    """
    Links corrective changes/commits from a git repository
    to changes that introduced the problem using git blame.
    """

    def __init__(self, repo_path: Path):
        """
        Constructor.
        Sets the repository path.
        """
        if not repo_path.is_dir():
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
            corrective_commit_hashes: A set of commit hashes identified as corrective.

        Returns:
            A dictionary where keys are the hashes of *buggy* (introducing) commits
            and values are lists of *corrective* commit hashes that fixed them.
            Example: {'buggy_hash1': ['fix_hash1', 'fix_hash2'], 'buggy_hash2': ['fix_hash3']}
        """
        bug_link_map: Dict[str, List[str]] = {} # buggy_hash -> [fixing_hash1, fixing_hash2,...]
        total_corrective = len(corrective_commits_info)
        processed_count = 0

        logger.info(f"Starting bug linking for {total_corrective} corrective commits...")

        # Get corrective hashes from the input dictionary keys
        corrective_commit_hashes = set(corrective_commits_info.keys())

        for corrective_hash in corrective_commit_hashes:
            processed_count += 1
            earliest_issue_ts = corrective_commits_info.get(corrective_hash) # Get timestamp for this hash

            if processed_count % 10 == 0 or processed_count == total_corrective:
                ts_info = f"(issue ts: {earliest_issue_ts})" if earliest_issue_ts else ""
                logger.info(f"Linking corrective commit {processed_count}/{total_corrective}: {corrective_hash[:7]} {ts_info}...")

            try:
                modified_regions = self._get_modified_regions(corrective_hash)
                if not modified_regions:
                    logger.debug(f"No modified code regions found or parsed for corrective commit {corrective_hash[:7]}.")
                    continue

                # Pass the timestamp to the annotation function
                introducing_commits = self._git_annotate_regions(
                    modified_regions, corrective_hash, earliest_issue_ts
                )

                for buggy_hash in introducing_commits:
                    if buggy_hash not in bug_link_map:
                        bug_link_map[buggy_hash] = []
                    if corrective_hash not in bug_link_map[buggy_hash]:
                         bug_link_map[buggy_hash].append(corrective_hash)

            except Exception as e:
                logger.error(f"Error linking corrective commit {corrective_hash[:7]}: {e}", exc_info=True)


        linked_count = len(bug_link_map)
        logger.info(f"Finished bug linking. Identified {linked_count} potential bug-introducing commits from {total_corrective} corrective commits.")
        if logger.isEnabledFor(logging.DEBUG) and bug_link_map:
            debug_map_str = json.dumps({k[:7]: [v[:7] for v in vals] for k, vals in list(bug_link_map.items())[:5]}, indent=2)
            logger.debug(f"Sample bug link map (buggy_hash -> [fixing_hashes]):\n{debug_map_str}")

        return bug_link_map

    def _get_modified_regions(self, commit_hash: str) -> Dict[str, List[int]]:
        """
        Gets files and line numbers modified/deleted in a commit compared to its parent.
        Focuses only on code files based on CODE_FILE_EXTENSIONS.
        """
        diff_cmd = f"git diff -U0 {commit_hash}^ {commit_hash}"
        files_cmd = f"git diff --name-only {commit_hash}^ {commit_hash}"

        try:
            diff_output = run_git_command(diff_cmd, cwd=self.repo_path)
            files_modified_output = run_git_command(files_cmd, cwd=self.repo_path)
            files_modified = set(fn for fn in files_modified_output.strip().splitlines() if fn) # Filter empty lines
        except subprocess.CalledProcessError as e:
            if "unknown revision" in e.stderr or "bad revision" in e.stderr:
                logger.warning(f"Could not get diff for commit {commit_hash[:7]} (likely initial commit or merge issue): {e.stderr.strip()}")
                return {}
            else:
                # Log but don't raise, return empty - allows task to continue maybe
                logger.error(f"Error getting git diff for {commit_hash[:7]}: {e.stderr.strip()}")
                return {} # Return empty dict on error
        except Exception as e:
            logger.error(f"Unexpected error getting diff/files for {commit_hash[:7]}: {e}", exc_info=True)
            return {} # Return empty dict on error

        return self._parse_diff_for_modified_lines(diff_output, files_modified)


    def _parse_diff_for_modified_lines(self, diff_output: str, files_modified: Set[str]) -> Dict[str, List[int]]:
        """Parses `git diff -U0` output for modified/deleted line numbers in known code files."""
        modified_lines_map: Dict[str, List[int]] = {}
        current_file: Optional[str] = None
        hunk_header_regex = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

        lines = diff_output.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1

            if line.startswith('diff --git'):
                match = re.match(r'diff --git a/(.*?) b/(.*)', line)
                if match:
                    # Use file path from 'a/' side for blaming parent
                    potential_file = match.group(1).strip()
                    if potential_file in files_modified:
                         file_ext_parts = potential_file.split('.')
                         # Check if it's a code file we care about
                         if len(file_ext_parts) > 1 and file_ext_parts[-1].upper() in CODE_FILE_EXTENSIONS:
                             current_file = potential_file
                             if current_file not in modified_lines_map:
                                 modified_lines_map[current_file] = []
                         else:
                              current_file = None # Skip non-code files
                    else:
                         current_file = None
                else:
                     current_file = None # If diff header format is unexpected

            elif line.startswith('@@') and current_file:
                hunk_match = hunk_header_regex.match(line)
                if hunk_match:
                    current_line_num_old = int(hunk_match.group(1))
                    while i < len(lines) and not lines[i].startswith(('diff --git', '@@ ')):
                        hunk_line = lines[i]
                        i += 1
                        # Only track lines removed from the old version
                        if hunk_line.startswith('-') and not hunk_line.startswith('---'):
                            modified_lines_map[current_file].append(current_line_num_old)
                            current_line_num_old += 1
                        elif hunk_line.startswith('+') and not hunk_line.startswith('+++'):
                            pass # Line added, ignore for blaming parent
                        else: # Context line (ignore with -U0) or other unexpected lines
                            # Only increment if it wasn't an added line
                             if not hunk_line.startswith('+'):
                                current_line_num_old += 1
                else:
                     logger.warning(f"Could not parse hunk header: {line} in file {current_file}")

        return {f: lines for f, lines in modified_lines_map.items() if lines} # Clean empty entries


    def _git_annotate_regions(
        self,
        regions: Dict[str, List[int]],
        corrective_commit_hash: str,
        earliest_issue_timestamp: Optional[int]
    ) -> Set[str]:
        """
        Uses `git blame` to find the origins of modified lines.
        Starts blame from commit before earliest issue timestamp if provided.
        If that fails due to "no such path", it falls back to blaming from
        the parent of the corrective commit.
        """
        introducing_commits: Set[str] = set()
        default_blame_start = f"{corrective_commit_hash}^"

        # --- Determine the initial starting commit for blame ---
        initial_blame_start_commit: Optional[str] = None
        used_issue_timestamp = False # Flag to know if we used the timestamp strategy initially

        if earliest_issue_timestamp:
            logger.debug(f"Using earliest issue timestamp {earliest_issue_timestamp} to find blame start for {corrective_commit_hash[:7]}")
            commit_before_issue = find_commit_hash_before_timestamp(self.repo_path, earliest_issue_timestamp)
            if commit_before_issue:
                initial_blame_start_commit = commit_before_issue
                used_issue_timestamp = True
                logger.info(f"Initial blame start for {corrective_commit_hash[:7]} set to commit before issue: {initial_blame_start_commit[:7]}")
            else:
                logger.warning(f"Could not find commit before issue timestamp {earliest_issue_timestamp} for {corrective_commit_hash[:7]}. Defaulting to parent.")
                initial_blame_start_commit = default_blame_start
        else:
            initial_blame_start_commit = default_blame_start
            logger.debug(f"Initial blame start for {corrective_commit_hash[:7]} set to parent: {initial_blame_start_commit[:7]}")
        # --- End determining initial start commit ---

        # Ensure initial_blame_start_commit is not None (should only happen if parent doesn't exist - initial commit case handled by _get_modified_regions returning {})
        if not initial_blame_start_commit:
             logger.error(f"Could not determine a valid blame start commit for {corrective_commit_hash[:7]}. Skipping blame.")
             return introducing_commits


        for file_path, line_numbers in regions.items():
            if not line_numbers: continue

            current_blame_start = initial_blame_start_commit
            attempt_fallback = False
            blame_succeeded = False

            logger.debug(f"Annotating file '{file_path}' for {len(line_numbers)} lines starting from {current_blame_start[:7]}")
            line_args = " ".join([f"-L {ln},{ln}" for ln in line_numbers])
            blame_cmd = f"git blame --porcelain -w {current_blame_start} {line_args} -- \"{file_path}\""

            try:
                blame_output = run_git_command(blame_cmd, cwd=self.repo_path)
                blame_succeeded = True # Mark as succeeded on first try

            except subprocess.CalledProcessError as e:
                 # Check if it's the "no such path" error AND we used the issue timestamp initially
                 is_no_such_path_error = "fatal: no such path" in e.stderr
                 if is_no_such_path_error and used_issue_timestamp and current_blame_start != default_blame_start:
                      logger.warning(f"Blame from issue-derived commit {current_blame_start[:7]} failed for '{file_path}' (no path). Attempting fallback from parent {default_blame_start[:7]}.")
                      attempt_fallback = True
                 elif "fatal: bad revision" in e.stderr:
                     logger.warning(f"Git blame failed for '{file_path}' at start {current_blame_start[:7]} (bad revision): {e.stderr.strip()}")
                     # Cannot fallback if parent is bad revision
                 else: # Other errors
                      logger.warning(f"Git blame command failed for '{file_path}', lines ~{line_numbers[0]} starting at {current_blame_start[:7]} for corrective {corrective_commit_hash[:7]}: {e.stderr.strip()}")
                      # Don't fallback on other errors for now
            except Exception as e:
                 logger.error(f"Unexpected error running initial git blame for {file_path} at {current_blame_start[:7]}: {e}", exc_info=True)
                 # Don't fallback

            # --- Fallback Attempt ---
            if attempt_fallback:
                current_blame_start = default_blame_start # Switch to parent
                logger.debug(f"Fallback: Annotating file '{file_path}' for {len(line_numbers)} lines starting from {current_blame_start[:7]}")
                blame_cmd = f"git blame --porcelain -w {current_blame_start} {line_args} -- \"{file_path}\""
                try:
                    blame_output = run_git_command(blame_cmd, cwd=self.repo_path)
                    blame_succeeded = True # Mark as succeeded on fallback
                except subprocess.CalledProcessError as e:
                     # Log fallback failure
                     logger.warning(f"Fallback git blame failed for '{file_path}' at start {current_blame_start[:7]}: {e.stderr.strip()}")
                     blame_succeeded = False # Ensure it's marked as failed
                except Exception as e:
                     logger.error(f"Unexpected error running fallback git blame for {file_path} at {current_blame_start[:7]}: {e}", exc_info=True)
                     blame_succeeded = False

            # --- Process Blame Output (if succeeded) ---
            if blame_succeeded:
                try:
                    current_hash = None
                    for line in blame_output.strip().splitlines():
                        parts = line.split()
                        # Check if the first part is a 40-char hash
                        if len(parts) > 0 and len(parts[0]) == 40 and all(c in '0123456789abcdef' for c in parts[0]):
                            current_hash = parts[0]
                        # Check if this line contains actual code content (heuristic: has a tab)
                        # and we have a hash associated with it
                        if current_hash and '\t' in line:
                            # Ensure we don't link the corrective commit itself or the commit we *started* blaming from
                            if current_hash != corrective_commit_hash and current_hash != current_blame_start:
                                introducing_commits.add(current_hash)
                            current_hash = None # Reset for the next potential blame block
                except Exception as parse_err:
                    logger.error(f"Error parsing blame output for {file_path} (start: {current_blame_start[:7]}): {parse_err}", exc_info=True)


        return introducing_commits
# ==================================================