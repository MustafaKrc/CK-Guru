# worker/ingestion/services/commit_state_tracker.py
import logging
from typing import Dict, List, Optional, Set, NamedTuple

from .git_log_parser import ParsedNumstatLine # Import from sibling module
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# --- Data Structures ---
class CommitFile:
    """Represents a file tracked across commits for metric calculation."""
    def __init__(self, name: str, loc: int, authors: List[str], lastchanged: int):
        self.name: str = name
        self.loc: int = loc
        self.authors: List[str] = authors # List of unique authors who touched this file
        self.lastchanged: int = lastchanged # Timestamp of last change
        self.nuc: int = 1 # Number of unique changes (commits) touching this file

    def __repr__(self):
        return f"<CommitFile(name='{self.name}', loc={self.loc}, lastchanged={self.lastchanged}, nuc={self.nuc})>"

class FileUpdateResult(NamedTuple):
    """Result of updating file state for a single file in a commit."""
    previous_loc: int
    previous_nuc: int
    time_diff_days: float
    authors_involved_before: Set[str] # Authors involved *before* this commit

class DevExperienceMetrics(NamedTuple):
    """Developer experience metrics calculated for a file interaction."""
    exp: int  # Total experience of the author *before* this commit
    rexp: float # Weighted experience (placeholder/approximation)
    sexp: int  # Subsystem experience of the author *before* this commit
# --- End Data Structures ---


class FileStateTracker:
    """Tracks the state (LOC, authors, NUC) of files across commits."""
    def __init__(self):
        self._file_states: Dict[str, CommitFile] = {}
        logger.debug("FileStateTracker initialized.")

    def update_file(
        self,
        parsed_line: ParsedNumstatLine,
        author: str,
        timestamp: int
    ) -> FileUpdateResult:
        """
        Updates the state for a single file based on a commit's numstat line.
        Modifies internal state (_file_states) IN PLACE.
        Returns metrics derived from the file's history *before* this update.
        """
        file_name = parsed_line.file_name
        file_la = parsed_line.la
        file_ld = parsed_line.ld

        previous_loc = 0
        previous_nuc = 0
        time_diff_days = 0.0
        authors_involved_before: Set[str] = set() # Authors who touched it before THIS commit

        if file_name in self._file_states:
            file_state = self._file_states[file_name]
            # --- Get state *before* update ---
            previous_loc = file_state.loc
            previous_nuc = file_state.nuc
            time_diff_seconds = timestamp - file_state.lastchanged
            time_diff_days = max(0, time_diff_seconds) / 86400.0 # Avoid negative age
            authors_involved_before.update(file_state.authors)

            # --- Update state ---
            file_state.loc += (file_la - file_ld)
            if author not in file_state.authors: # Add author if new to this file
                 file_state.authors.append(author)
            file_state.lastchanged = timestamp
            file_state.nuc += 1
        else:
            # New file: previous state metrics are 0
            authors_involved_before.add(author) # Author is involved now
            self._file_states[file_name] = CommitFile(
                name=file_name,
                loc=(file_la - file_ld),
                authors=[author], # Start with current author
                lastchanged=timestamp
                # nuc defaults to 1 in CommitFile constructor
            )

        return FileUpdateResult(previous_loc, previous_nuc, time_diff_days, authors_involved_before)

    def get_current_file_state(self, file_name: str) -> Optional[CommitFile]:
        """Returns the current state of a file, if tracked."""
        return self._file_states.get(file_name)


class DeveloperExperienceTracker:
    """Tracks developer experience (total and per subsystem) across commits."""
    def __init__(self):
        # Structure: {author_name: {subsystem_name: commit_count}}
        self._dev_states: Dict[str, Dict[str, int]] = {}
        logger.debug("DeveloperExperienceTracker initialized.")

    def update_experience(
        self,
        author: str,
        subsystem: str
    ) -> DevExperienceMetrics:
        """
        Updates developer experience state based on a commit in a subsystem.
        Modifies internal state (_dev_states) IN PLACE.
        Returns experience metrics *before* this update.
        """
        exp = 0
        sexp = 0
        rexp = 0.0 # Placeholder - REXP definition needs refinement, using EXP for now

        # --- Calculate metrics *before* updating state ---
        if author in self._dev_states:
            author_exp_map = self._dev_states[author]
            exp = sum(author_exp_map.values()) # Total exp = sum of subsystem counts
            sexp = author_exp_map.get(subsystem, 0) # Subsystem exp = count for this subsystem
            # REXP approximation (replace with actual formula if defined)
            rexp = float(exp / (exp + 1)) if exp > 0 else 0.0 # Example weighted exp
        # else: exp, sexp, rexp remain 0 for the first commit by this author

        # --- Update state *after* calculating metrics ---
        if author not in self._dev_states:
            self._dev_states[author] = {}
        self._dev_states[author][subsystem] = self._dev_states[author].get(subsystem, 0) + 1

        return DevExperienceMetrics(exp, rexp, sexp)

    def get_author_experience(self, author: str) -> Optional[Dict[str, int]]:
        """Returns the current experience map for an author."""
        return self._dev_states.get(author)