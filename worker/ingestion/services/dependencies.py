# worker/ingestion/dependencies/dependencies.py
import logging
from typing import Dict, Any, Type, Callable, Optional
from sqlalchemy.orm import Session

# --- Interfaces ---
from services.interfaces.i_git_service import IGitService
from services.interfaces.i_ck_runner_service import ICKRunnerService
from services.interfaces.i_repository_api_client import IRepositoryApiClient
from shared.services.interfaces import IJobStatusUpdater

# --- Concrete Implementations ---
from services.git_service import GitService
from services.ck_runner_service import CKRunnerService
from services.github_client import GitHubClient # Default Repo API client
# from services.gitlab_client import GitLabClient # Hypothetical future client
from shared.services import JobStatusUpdater
from services.bug_linker import GitCommitLinker

# --- Steps ---
from services.steps.base import IngestionStep, IngestionContext
from services.steps.prepare_repo import PrepareRepositoryStep
from services.steps.calculate_guru import CalculateCommitGuruMetricsStep
from services.steps.persist_guru import PersistCommitGuruMetricsStep
from services.steps.fetch_link_issues import FetchAndLinkIssuesStep
from services.steps.link_bugs import LinkBugsStep
from services.steps.calculate_ck import CalculateCKMetricsStep
from services.steps.persist_ck import PersistCKMetricsStep
from services.steps.resolve_commit_hashes import ResolveCommitHashesStep
from services.steps.ensure_commits_exist import EnsureCommitsExistLocallyStep

from services.factories import RepositoryFactory


from shared.core.config import settings 

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Simple Step Registry
class StepRegistry:
    """Instantiates and provides step instances."""
    def __init__(self):
        # Cache instances if they are stateless, otherwise create new ones
        self._instances = {}
        # Map class to potentially cached instance
        self._step_map: Dict[Type[IngestionStep], IngestionStep] = {}

    def get_step(self, step_class: Type[IngestionStep]) -> IngestionStep:
        # Simple instantiation for now, assumes steps are stateless or manage state via context
        if step_class not in self._step_map:
             try:
                  self._step_map[step_class] = step_class() # Instantiate the step
                  logger.debug(f"Instantiated step: {step_class.__name__}")
             except Exception as e:
                  logger.error(f"Failed to instantiate step {step_class.__name__}: {e}", exc_info=True)
                  raise
        return self._step_map[step_class]


class DependencyProvider:
    """Provides various dependencies needed by pipeline steps."""
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        self.repo_factory = RepositoryFactory(session_factory)
        self.ck_runner = CKRunnerService()
        self.job_status_updater = JobStatusUpdater(session_factory)

        # --- Cache for Singleton-like services within the provider's scope ---
        self._cached_services: Dict[Type, Any] = {}
        # --- Pre-instantiate truly global/stateless singletons  ---
        self._cached_services[ICKRunnerService] = CKRunnerService()
        self._cached_services[IJobStatusUpdater] = JobStatusUpdater(session_factory)

    # --- Factory Method for GitService (Context-Dependent) ---
    def _get_git_service(self, context: IngestionContext) -> IGitService:
        """Creates or gets a GitService instance for the specific repo path."""
        # Could add caching based on context.repo_local_path if multiple steps
        # in the same run needed it, but likely fine to create new each time.
        if not context.repo_local_path:
             raise ValueError("Cannot instantiate GitService: repo_local_path missing from context.")
        return GitService(context.repo_local_path) # Always returns concrete GitService for now

    # --- Factory Method for Repository API Client (Context/Config-Dependent) ---
    def _get_repository_api_client(self, context: IngestionContext) -> IRepositoryApiClient:
        """Creates the appropriate API client based on context or config."""
        if IRepositoryApiClient in self._cached_services:
            return self._cached_services[IRepositoryApiClient]

        if not context.git_url:
            repo_repo = self.repo_factory.get_repository_repo()
            repo_meta = repo_repo.get_by_id(context.repository_id)
            if repo_meta is None:
                raise ValueError(f"Repository {context.repository_id} not found")
            context.git_url = repo_meta.git_url.lower()
        

        if "github.com" in context.git_url:
            client = GitHubClient()
        # elif "gitlab.com" in git_url:
        #     client = GitLabClient()
        else:
            raise ValueError(f"Unsupported provider for URL: {git_url}")

        self._cached_services[IRepositoryApiClient] = client
        return client


    # --- Factory Method for CK Runner ---
    def _get_ck_runner_service(self) -> ICKRunnerService:
        """Returns the configured CK Runner service instance."""
        # Currently simple, just returns cached instance
        return self._cached_services[ICKRunnerService]

    # --- Factory Method for Job Status Updater ---
    def _get_job_status_updater(self) -> IJobStatusUpdater:
        """Returns the Job Status Updater instance."""
        return self._cached_services[IJobStatusUpdater]

    # --- Factory Method for Bug Linker (Context-Dependent) ---
    def _get_bug_linker(self, context: IngestionContext, git_service: IGitService) -> GitCommitLinker:
         """Creates a GitCommitLinker instance."""
         if not context.repo_local_path:
              raise ValueError("Cannot instantiate GitCommitLinker: repo_local_path missing.")
         # Linker requires concrete GitService currently, or update its __init__ type hint
         if not isinstance(git_service, GitService):
              # This check might be too strict if mocks are used, consider removing in testing
              logger.warning("GitCommitLinker initialized with non-concrete GitService implementation.")
         return GitCommitLinker(context.repo_local_path, git_service)

    def get_dependencies_for_step(self, step: IngestionStep, context: IngestionContext) -> Dict[str, Any]:
        """Returns a dictionary of dependencies required by the given step."""
        deps = {}
        step_type = type(step)

        # Provide repositories based on step type

        if step_type == PersistCommitGuruMetricsStep:
            deps['guru_repo'] = self.repo_factory.get_commit_guru_repo()
        elif step_type == PersistCKMetricsStep:
            deps['ck_repo'] = self.repo_factory.get_ck_metric_repo()
        elif step_type == FetchAndLinkIssuesStep:
            deps['github_repo'] = self.repo_factory.get_github_issue_repo()
            deps['guru_repo'] = self.repo_factory.get_commit_guru_repo()
            deps['repository_api_client'] = self._get_repository_api_client(context)
        elif step_type == LinkBugsStep:
            deps['guru_repo'] = self.repo_factory.get_commit_guru_repo()
            deps['git_service'] = self._get_git_service(context)
        elif step_type == PersistCKMetricsStep:
            deps['ck_repo'] = self.repo_factory.get_ck_metric_repo()
        elif step_type == CalculateCKMetricsStep:
            deps['ck_runner'] = self.ck_runner
            deps['ck_repo'] = self.repo_factory.get_ck_metric_repo()
            deps['git_service'] = self._get_git_service(context)
        elif step_type == CalculateCommitGuruMetricsStep:
            deps['git_service'] = self._get_git_service(context)
        elif step_type == PrepareRepositoryStep:
            # We could provide a GitService instance here 
            # but the step prepares the repo and GitService requires the repo to be presesent
            pass
        elif step_type == EnsureCommitsExistLocallyStep:
            deps['git_service'] = self._get_git_service(context)
        elif step_type == ResolveCommitHashesStep:
            deps['git_service'] = self._get_git_service(context)


        logger.debug(f"Providing dependencies for step {step.__class__.__name__}: {list(deps.keys())}")
        return deps

    # --- Pass through UoW methods ---
    def start_unit_of_work(self):
        self.repo_factory.start_unit_of_work()

    def commit_unit_of_work(self):
        self.repo_factory.commit_unit_of_work()

    def rollback_unit_of_work(self):
        self.repo_factory.rollback_unit_of_work()