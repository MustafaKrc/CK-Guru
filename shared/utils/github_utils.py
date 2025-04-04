# worker/app/tasks/utils/github_utils.py
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple, NamedTuple
from datetime import datetime

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from shared.core.config import settings # Access settings for token

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Regex to find GitHub issue numbers like #123
ISSUE_ID_REGEX = re.compile(r'#(\d+)')
GITHUB_API_BASE = "https://api.github.com"

MAX_RATE_LIMIT_RETRIES = 5 # Max times to wait for rate limit reset for a single request
RATE_LIMIT_BUFFER_SECONDS = 10 # Extra seconds to wait after reset time

# Simple owner/repo extraction (might need refinement for complex URLs)
REPO_URL_REGEX = re.compile(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$')

# --- Structures for API Response ---
class GitHubAPIResponse(NamedTuple):
    status_code: int
    etag: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None
    error_message: Optional[str] = None # Add field for error details

def extract_repo_owner_name(git_url: str) -> Optional[Tuple[str, str]]:
    """Extracts owner and repo name from a GitHub URL."""
    match = REPO_URL_REGEX.search(git_url)
    if match:
        owner, repo_name = match.groups()
        return owner, repo_name
    logger.warning(f"Could not extract owner/repo from URL: {git_url}")
    return None

class GitHubIssueFetcher:
    """Fetches issue data from the GitHub API."""

    def __init__(self, token: Optional[str] = settings.GITHUB_TOKEN):
        self.token = token
        self.session = requests.Session()
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        else:
            logger.warning("No GitHub token provided. API requests will be unauthenticated and heavily rate-limited.")
        self.session.headers.update(headers)

    def _parse_rate_limit_headers(self, headers: requests.structures.CaseInsensitiveDict) -> Tuple[Optional[int], Optional[int]]:
        """Parses rate limit headers safely."""
        remaining, reset_timestamp = None, None
        remaining_str = headers.get('X-RateLimit-Remaining')
        reset_str = headers.get('X-RateLimit-Reset')
        if remaining_str is not None:
            try:
                remaining = int(remaining_str)
            except ValueError:
                logger.warning(f"Could not parse X-RateLimit-Remaining header: {remaining_str}")
        if reset_str is not None:
            try:
                reset_timestamp = int(reset_str)
            except ValueError:
                logger.warning(f"Could not parse X-RateLimit-Reset header: {reset_str}")
        return remaining, reset_timestamp

    def _make_request(self, url: str, etag: Optional[str] = None) -> GitHubAPIResponse:
        """
        Makes a request to the GitHub API, handling rate limits and ETags.
        Returns a structured GitHubAPIResponse.
        """
        current_headers = self.session.headers.copy()
        if etag:
            current_headers['If-None-Match'] = etag

        rate_limit_retries = 0
        while True: # Loop for handling rate limit waits
            remaining, reset_timestamp = None, None # Reset for each attempt
            try:
                response = self.session.get(url, headers=current_headers, timeout=20)
                remaining, reset_timestamp = self._parse_rate_limit_headers(response.headers)

                logger.debug(f"GitHub API: {url} - Status: {response.status_code}, ETag: {etag}, Remaining: {remaining}")

                # --- Rate Limit Handling (Primary Trigger: 403 with remaining=0) ---
                if response.status_code == 403 and remaining == 0:
                    rate_limit_retries += 1
                    if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                        msg = f"GitHub rate limit exceeded and max retries ({MAX_RATE_LIMIT_RETRIES}) reached for {url}."
                        logger.error(msg)
                        # Return specific status code or marker? Let's return the 403
                        return GitHubAPIResponse(
                            status_code=403, rate_limit_remaining=remaining,
                            rate_limit_reset=reset_timestamp, error_message=msg
                        )

                    current_time = time.time()
                    wait_seconds = max(0, (reset_timestamp or current_time) - current_time) + RATE_LIMIT_BUFFER_SECONDS
                    reset_dt = datetime.fromtimestamp(reset_timestamp) if reset_timestamp else "N/A"
                    logger.warning(
                        f"GitHub rate limit hit for {url}. Waiting {wait_seconds:.1f}s "
                        f"(until ~{reset_dt}). Retry {rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES}."
                    )
                    time.sleep(wait_seconds)
                    logger.info(f"Resuming GitHub API requests after rate limit wait.")
                    continue # Retry the request

                # --- ETag Handling ---
                response_etag = response.headers.get('ETag')
                if response.status_code == 304: # Not Modified
                    logger.debug(f"GitHub API: 304 Not Modified for {url} (ETag: {etag})")
                    return GitHubAPIResponse(
                        status_code=304, etag=response_etag or etag, # Return new or original ETag
                        rate_limit_remaining=remaining, rate_limit_reset=reset_timestamp
                    )

                # --- Other Status Codes ---
                # Check for other errors *after* 304/403 rate limit
                response.raise_for_status() # Raises HTTPError for 4xx/5xx other than 304/403 handled above

                # --- Success (200 OK) ---
                return GitHubAPIResponse(
                    status_code=200,
                    etag=response_etag,
                    json_data=response.json(),
                    rate_limit_remaining=remaining,
                    rate_limit_reset=reset_timestamp
                )

            # --- Exception Handling ---
            except Timeout:
                msg = f"GitHub API request timed out for {url}."
                logger.error(msg)
                return GitHubAPIResponse(status_code=408, error_message=msg) # 408 Request Timeout
            except ConnectionError as e:
                msg = f"GitHub API connection error for {url}: {e}"
                logger.error(msg)
                return GitHubAPIResponse(status_code=503, error_message=msg) # 503 Service Unavailable (example)
            except RequestException as e:
                # Handle non-2xx/304/403 responses that raise_for_status catches, or other RequestExceptions
                status_code = e.response.status_code if e.response is not None else 500
                err_content = e.response.text[:200] if e.response is not None else str(e)
                msg = f"GitHub API request failed for {url}: Status {status_code}, Error: {err_content}"
                logger.error(msg)
                # Return the actual status code from the response if available
                return GitHubAPIResponse(
                    status_code=status_code,
                    error_message=msg,
                    rate_limit_remaining=remaining, # Include rate limits even on error if available
                    rate_limit_reset=reset_timestamp
                )
            except Exception as e:
                # Catch any other unexpected error during the request/wait
                msg = f"Unexpected error during GitHub request/wait for {url}: {e}"
                logger.exception(msg) # Use exception() to include traceback
                return GitHubAPIResponse(status_code=500, error_message=msg) # 500 Internal Server Error
        

    def get_issue_data(self, owner: str, repo_name: str, issue_number: str, current_etag: Optional[str] = None) -> GitHubAPIResponse:
        """
        Fetches data for a specific issue using ETags for caching.
        Returns a GitHubAPIResponse object.
        """
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/issues/{issue_number}"
        logger.debug(f"Fetching GitHub issue: {owner}/{repo_name}#{issue_number} with ETag: {current_etag}")
        return self._make_request(api_url, etag=current_etag)


def extract_issue_ids(message: Optional[str]) -> List[str]:
    """Extracts unique issue IDs (digits only) from a commit message."""
    if not message:
        return []
    # Find all occurrences like #123, #45 etc.
    ids = ISSUE_ID_REGEX.findall(message)
    return sorted(list(set(ids)), key=int) # Return unique IDs sorted numerically