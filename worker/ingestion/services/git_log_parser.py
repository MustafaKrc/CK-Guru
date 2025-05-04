# worker/ingestion/services/git_log_parser.py
import re
import logging
from typing import Any, Dict, List, Optional, NamedTuple

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# --- Constants ---
COMMIT_GURU_LOG_FORMAT = (
    '--pretty=format:\"<CAS_COMMIT_START>'
    '<CAS_FIELD>parent_hashes<CAS_DELIM>%P<CAS_END>'
    '<CAS_FIELD>commit_hash<CAS_DELIM>%H<CAS_END>'
    '<CAS_FIELD>author_name<CAS_DELIM>%an<CAS_END>'
    '<CAS_FIELD>author_email<CAS_DELIM>%ae<CAS_END>'
    '<CAS_FIELD>author_date<CAS_DELIM>%ad<CAS_END>'
    '<CAS_FIELD>author_date_unix_timestamp<CAS_DELIM>%at<CAS_END>'
    '<CAS_FIELD>commit_message<CAS_DELIM>%B%n<CAS_END>' # %B includes subject and body
    '<CAS_COMMIT_END>\" --numstat --reverse --encoding=UTF-8'
    # Consider adding --no-merges if needed
)
# --- End Constants ---


# --- Data Structures ---
class ParsedNumstatLine(NamedTuple):
    """Structured data from a parsed --numstat line."""
    la: int
    ld: int
    file_name: str
    subsystem: str
    directory: str
# --- End Data Structures ---


class GitLogParser:
    """Parses custom formatted git log output including numstat."""

    _COMMIT_REGEX = re.compile(r"(.*?)<CAS_COMMIT_END>(.*)", re.DOTALL)
    _FIELD_REGEX = re.compile(r"<CAS_FIELD>(.*?)<CAS_DELIM>(.*?)<CAS_END>", re.DOTALL)

    def parse_custom_log(self, log_output: str) -> List[Dict[str, Any]]:
        """Parses the custom formatted git log output."""
        commits_data = []
        # Split commits, skipping potential empty string before the first marker
        commit_blobs = log_output.strip().split('<CAS_COMMIT_START>')
        if not commit_blobs or (len(commit_blobs) == 1 and not commit_blobs[0]):
            logger.warning("Log output does not contain any commit markers or is empty.")
            return []

        for blob in commit_blobs:
            if not blob.strip(): # Skip empty blobs (e.g., the one before first marker)
                continue

            match = self._COMMIT_REGEX.match(blob)
            if not match:
                logger.warning(f"Could not parse commit blob structure: {blob[:100]}...")
                continue

            pretty_part = match.group(1)
            stats_part = match.group(2).strip()
            commit_info = {}

            for field_match in self._FIELD_REGEX.finditer(pretty_part):
                key = field_match.group(1).strip()
                # Remove potential trailing newline from commit message
                value = field_match.group(2).strip()
                commit_info[key] = value

            if 'commit_hash' not in commit_info:
                logger.warning(f"Parsed commit blob missing commit_hash: {pretty_part}")
                continue

            # Store raw stats lines for later parsing by parse_numstat_line
            commit_info['stats_lines'] = stats_part.splitlines()
            commits_data.append(commit_info)

        logger.info(f"GitLogParser: Parsed {len(commits_data)} commits from log output.")
        return commits_data

    def parse_numstat_line(self, line: str, commit_hash_debug: str) -> Optional[ParsedNumstatLine]:
        """Parses a single --numstat line, returning structured data or None."""
        if not line or not line.strip(): # Check for empty or whitespace-only lines
            return None

        parts = line.split('\t')
        if len(parts) != 3:
            # Log only if it's not an empty line we already checked
            if line.strip(): logger.warning(f"Skipping malformed numstat line (parts!=3): '{line}' in commit {commit_hash_debug}")
            return None

        la_str, ld_str, file_path_raw = parts

        # Handle binary file changes indicated by '-'
        try:
            file_la = 0 if la_str == '-' else int(la_str)
            file_ld = 0 if ld_str == '-' else int(ld_str)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse LA/LD '{la_str}/{ld_str}' for file path '{file_path_raw}' in commit {commit_hash_debug}. Skipping file.")
            return None

        # Clean file path: strip quotes, whitespace
        file_name = file_path_raw.strip().strip("'").strip('"')

        # Handle potential rename syntax like 'old/path => new/path' or '{old=>new}/path'
        # We typically care about the *new* path after the commit for metrics.
        if ' => ' in file_name:
             # Simple rename: old/path => new/path
             file_name = file_name.split(' => ')[-1]
        elif '{' in file_name and '=>' in file_name and '}' in file_name:
             # Path segment rename: path/{old=>new}/file
             # This requires more complex parsing to reconstruct the new path.
             # For simplicity, we might just take the part after '=>' if it looks like a path,
             # or log a warning and skip. Let's try a simple extraction.
             match = re.search(r'{(.*)=>(.*)}', file_name)
             if match:
                  old_part, new_part = match.groups()
                  # Reconstruct, hoping this covers common cases
                  file_name = file_name.replace(match.group(0), new_part)
                  logger.debug(f"Processed rename syntax '{file_path_raw}' to '{file_name}'")
             else:
                  logger.warning(f"Could not reliably parse rename syntax: '{file_path_raw}'. Using raw path.")
                  # Keep file_name as is, might cause issues later

        if not file_name: # Check if empty after cleaning
            return None

        # Determine subsystem/directory
        file_parts = file_name.split('/')
        subsystem = file_parts[0] if len(file_parts) > 1 else "root" # Use root if no '/'
        directory = "/".join(file_parts[:-1]) if len(file_parts) > 1 else "root"

        return ParsedNumstatLine(file_la, file_ld, file_name, subsystem, directory)