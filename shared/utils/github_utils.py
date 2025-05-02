# shared/utils/github_utils.py
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple, NamedTuple
from datetime import datetime

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from requests.structures import CaseInsensitiveDict # Import specific type

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Constants moved inside or made private if only used by the class
_ISSUE_ID_REGEX = re.compile(r'#(\d+)')
_GITHUB_API_BASE = "https://api.github.com"
_MAX_RATE_LIMIT_RETRIES = 5
_RATE_LIMIT_BUFFER_SECONDS = 10
_REPO_URL_REGEX = re.compile(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$')


# --- Structures for API Response ---
class GitHubAPIResponse(NamedTuple):
    status_code: int
    etag: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None
    error_message: Optional[str] = None

# --- Standalone Helper Functions (can be moved inside class if preferred) ---
def extract_repo_owner_name(git_url: str) -> Optional[Tuple[str, str]]:
    """Extracts owner and repo name from a GitHub URL."""
    match = _REPO_URL_REGEX.search(git_url)
    if match:
        owner, repo_name = match.groups()
        return owner, repo_name
    logger.warning(f"Could not extract owner/repo from URL: {git_url}")
    return None

def extract_issue_ids(message: Optional[str]) -> List[str]:
    """Extracts unique issue IDs (digits only) from a commit message."""
    if not message:
        return []
    ids = _ISSUE_ID_REGEX.findall(message)
    # Return unique IDs sorted numerically
    return sorted(list(set(ids)), key=int)


# --- GitHub Client Class ---
class GitHubClient:
    """Fetches data from the GitHub API, handling rate limits and ETags."""

    def __init__(self, token: Optional[str] = settings.GITHUB_TOKEN):
        self.token = token
        self.session = requests.Session()
        headers = {'Accept': 'application/vnd.github.v3+json', 'X-GitHub-Api-Version': '2022-11-28'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}' # Use Bearer token
        else:
            logger.warning("No GitHub token provided. API requests will be unauthenticated and heavily rate-limited.")
        self.session.headers.update(headers)
        logger.debug("GitHubClient initialized.")

    def _parse_rate_limit_headers(self, headers: CaseInsensitiveDict) -> Tuple[Optional[int], Optional[int]]:
        """Parses rate limit headers safely."""
        remaining, reset_timestamp = None, None
        # Use lowercase keys for consistency with CaseInsensitiveDict behavior
        remaining_str = headers.get('x-ratelimit-remaining')
        reset_str = headers.get('x-ratelimit-reset')
        if remaining_str is not None:
            try: remaining = int(remaining_str)
            except ValueError: logger.warning(f"Could not parse X-RateLimit-Remaining: {remaining_str}")
        if reset_str is not None:
            try: reset_timestamp = int(reset_str)
            except ValueError: logger.warning(f"Could not parse X-RateLimit-Reset: {reset_str}")
        return remaining, reset_timestamp

    def _make_request(self, method: str, url: str, etag: Optional[str] = None, **kwargs) -> GitHubAPIResponse:
        """
        Makes a request to the GitHub API, handling rate limits and ETags.
        Returns a structured GitHubAPIResponse.
        """
        current_headers = self.session.headers.copy()
        if etag:
            current_headers['If-None-Match'] = etag

        rate_limit_retries = 0
        while True: # Loop for rate limit waits
            remaining, reset_timestamp = None, None
            try:
                response = self.session.request(method, url, headers=current_headers, timeout=25, **kwargs)
                remaining, reset_timestamp = self._parse_rate_limit_headers(response.headers)
                logger.debug(f"GitHub API: {method} {url} - Status: {response.status_code}, ETag: {etag}, Remaining: {remaining}")

                # --- Rate Limit Handling ---
                if response.status_code == 403 and remaining == 0:
                    rate_limit_retries += 1
                    if rate_limit_retries > _MAX_RATE_LIMIT_RETRIES:
                        msg = f"GitHub rate limit max retries ({_MAX_RATE_LIMIT_RETRIES}) reached for {url}."
                        logger.error(msg)
                        return GitHubAPIResponse(403, rate_limit_remaining=0, rate_limit_reset=reset_timestamp, error_message=msg)

                    current_time = time.time()
                    wait_seconds = max(0, (reset_timestamp or current_time) - current_time) + _RATE_LIMIT_BUFFER_SECONDS
                    reset_dt = datetime.fromtimestamp(reset_timestamp) if reset_timestamp else "N/A"
                    logger.warning(f"GitHub rate limit hit. Waiting {wait_seconds:.1f}s (until ~{reset_dt}). Retry {rate_limit_retries}/{_MAX_RATE_LIMIT_RETRIES}.")
                    time.sleep(wait_seconds)
                    logger.info("Resuming GitHub API requests.")
                    continue # Retry

                # --- ETag Handling (for GET requests) ---
                response_etag = response.headers.get('ETag')
                if method.upper() == 'GET' and response.status_code == 304:
                    logger.debug(f"GitHub API: 304 Not Modified for {url} (ETag: {etag})")
                    return GitHubAPIResponse(304, etag=response_etag or etag, rate_limit_remaining=remaining, rate_limit_reset=reset_timestamp)

                # --- Other Status Codes ---
                response.raise_for_status() # Raises HTTPError for 4xx/5xx not handled above

                # --- Success (2xx) ---
                json_data = None
                if response.content and response.headers.get('Content-Type', '').startswith('application/json'):
                     try: json_data = response.json()
                     except requests.exceptions.JSONDecodeError: logger.warning(f"Failed to decode JSON response from {url}")

                return GitHubAPIResponse(
                    status_code=response.status_code, # Usually 200, 201, 204 etc.
                    etag=response_etag,
                    json_data=json_data,
                    rate_limit_remaining=remaining,
                    rate_limit_reset=reset_timestamp
                )

            # --- Exception Handling ---
            except Timeout:
                msg = f"GitHub API request timed out for {method} {url}."
                logger.error(msg)
                return GitHubAPIResponse(status_code=408, error_message=msg) # 408 Request Timeout
            except ConnectionError as e:
                msg = f"GitHub API connection error for {method} {url}: {e}"
                logger.error(msg)
                return GitHubAPIResponse(status_code=503, error_message=msg) # 503 Service Unavailable
            except RequestException as e:
                status_code = e.response.status_code if e.response is not None else 500
                err_content = e.response.text[:200] if e.response is not None else str(e)
                msg = f"GitHub API request failed for {method} {url}: Status {status_code}, Error: {err_content}"
                logger.error(msg)
                return GitHubAPIResponse(status_code=status_code, error_message=msg, rate_limit_remaining=remaining, rate_limit_reset=reset_timestamp)
            except Exception as e:
                msg = f"Unexpected error during GitHub request for {method} {url}: {e}"
                logger.exception(msg)
                return GitHubAPIResponse(status_code=500, error_message=msg)

    def get_issue(self, owner: str, repo_name: str, issue_number: str, current_etag: Optional[str] = None) -> GitHubAPIResponse:
        """
        Fetches data for a specific issue using ETags for caching.
        """
        api_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo_name}/issues/{issue_number}"
        logger.debug(f"GitHubClient: Fetching issue {owner}/{repo_name}#{issue_number} with ETag: {current_etag}")
        return self._make_request("GET", api_url, etag=current_etag)

    # --- Add other methods as needed ---
    # def get_commit(self, owner: str, repo_name: str, commit_sha: str) -> GitHubAPIResponse:
    #     api_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo_name}/commits/{commit_sha}"
    #     return self._make_request("GET", api_url)