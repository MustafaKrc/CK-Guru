# worker/ingestion/services/strategies/strategies.py
import logging
from abc import ABC, abstractmethod
from typing import List, Type

# Import step base class for type hinting if needed, but preferably use keys
# from services.steps.base import IngestionStep
# Import step classes (or define keys)
from services.steps.prepare_repo import PrepareRepositoryStep
from services.steps.calculate_guru import CalculateCommitGuruMetricsStep
from services.steps.persist_guru import PersistCommitGuruMetricsStep
from services.steps.fetch_link_issues import FetchAndLinkIssuesStep
from services.steps.link_bugs import LinkBugsStep
from services.steps.calculate_ck import CalculateCKMetricsStep
from services.steps.persist_ck import PersistCKMetricsStep
from services.steps.resolve_commit_hashes import ResolveCommitHashesStep
from services.steps.ensure_commits_exist import EnsureCommitsExistLocallyStep

logger = logging.getLogger(__name__)

# Define Step Keys/Identifiers (Using class names for now, could be strings)
STEP_PREPARE_REPO = PrepareRepositoryStep
STEP_CALCULATE_GURU = CalculateCommitGuruMetricsStep
STEP_PERSIST_GURU = PersistCommitGuruMetricsStep
STEP_FETCH_LINK_ISSUES = FetchAndLinkIssuesStep
STEP_LINK_BUGS = LinkBugsStep
STEP_CALCULATE_CK = CalculateCKMetricsStep
STEP_PERSIST_CK = PersistCKMetricsStep
STEP_RESOLVE_HASHES = ResolveCommitHashesStep
STEP_ENSURE_COMMITS =  EnsureCommitsExistLocallyStep

class IngestionStrategy(ABC):
    """Abstract base class for defining an ingestion pipeline strategy."""

    @abstractmethod
    def get_steps(self) -> List[Type['IngestionStep']]: # Return list of Step classes/types
        """Returns the ordered list of step types for this strategy."""
        pass

class FullHistoryIngestionStrategy(IngestionStrategy):
    """Strategy for ingesting the full repository history."""

    def get_steps(self) -> List[Type['IngestionStep']]:
        logger.debug("Using FullHistoryIngestionStrategy")
        return [
            STEP_PREPARE_REPO,
            STEP_CALCULATE_GURU,
            STEP_PERSIST_GURU,
            STEP_FETCH_LINK_ISSUES,
            STEP_LINK_BUGS,
            STEP_CALCULATE_CK,
            STEP_PERSIST_CK
        ]

class SingleCommitFeatureExtractionStrategy(IngestionStrategy):
    """Strategy for extracting features for a single commit inference."""

    def get_steps(self) -> List[Type['IngestionStep']]:
        logger.debug("Using SingleCommitFeatureExtractionStrategy")
        return [
            STEP_PREPARE_REPO,
            STEP_RESOLVE_HASHES,
            STEP_ENSURE_COMMITS,
            STEP_CALCULATE_GURU,
            STEP_PERSIST_GURU,     
            STEP_FETCH_LINK_ISSUES,
            STEP_LINK_BUGS,
            STEP_CALCULATE_CK,
            STEP_PERSIST_CK   
        ]