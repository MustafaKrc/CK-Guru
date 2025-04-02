# worker/app/tasks/utils/github_utils.py
from datetime import datetime
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from functools import lru_cache # Use standard library cache

import requests
import dateutil.parser
from requests.exceptions import RequestException, Timeout, ConnectionError

from ...core.config import settings # Access settings for token

logger = logging.getLogger(__name__)

# Regex to find GitHub issue numbers like #123
ISSUE_ID_REGEX = re.compile(r'#(\d+)')
GITHUB_API_BASE = "https://api.github.com"

MAX_RATE_LIMIT_RETRIES = 5 # Max times to wait for rate limit reset for a single request
RATE_LIMIT_BUFFER_SECONDS = 10 # Extra seconds to wait after reset time

# Simple owner/repo extraction (might need refinement for complex URLs)
REPO_URL_REGEX = re.compile(r'github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?$')

def _extract_repo_owner_name(git_url: str) -> Optional[Tuple[str, str]]:
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
        if self.token:
            self.session.headers.update({'Authorization': f'token {self.token}'})
        else:
            logger.warning("No GitHub token provided. API requests will be unauthenticated and heavily rate-limited.")
        self.session.headers.update({'Accept': 'application/vnd.github.v3+json'})

    def _make_request(self, url: str) -> Optional[Dict[str, Any]]: # Return Optional in case of failure after retries
        """
        Makes a request to the GitHub API, handling rate limits with waits/retries.
        Returns parsed JSON data or None if the request fails after retries.
        """
        rate_limit_retries = 0
        while True: # Loop for handling rate limit waits
            try:
                response = self.session.get(url, timeout=20) # Increased timeout slightly

                # --- Rate Limit Handling ---
                remaining_str = response.headers.get('X-RateLimit-Remaining')
                reset_str = response.headers.get('X-RateLimit-Reset')
                remaining = -1
                reset_timestamp = 0

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

                logger.debug(f"GitHub API Rate Limit: {remaining} remaining. Resets at {datetime.fromtimestamp(reset_timestamp) if reset_timestamp > 0 else 'N/A'}.")

                if response.status_code == 403 and remaining == 0:
                    rate_limit_retries += 1
                    if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                         logger.error(f"GitHub rate limit exceeded and maximum retries ({MAX_RATE_LIMIT_RETRIES}) reached for URL: {url}. Giving up on this request.")
                         return None # Give up on this specific request

                    # Calculate wait time
                    current_time = time.time()
                    wait_seconds = max(0, reset_timestamp - current_time) + RATE_LIMIT_BUFFER_SECONDS

                    wait_minutes = wait_seconds / 60
                    reset_dt = datetime.fromtimestamp(reset_timestamp) if reset_timestamp > 0 else "N/A"
                    logger.warning(f"GitHub rate limit hit for {url}. Waiting for {wait_seconds:.1f} seconds (until ~{reset_dt}). Retry {rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES}.")
                    time.sleep(wait_seconds)
                    logger.info(f"Resuming GitHub API requests after rate limit wait.")
                    continue # Retry the request

                # --- End Rate Limit Handling ---

                response.raise_for_status() # Raise HTTPError for other bad responses (4xx, 5xx)
                return response.json() # Success! Return JSON data

            except Timeout:
                logger.error(f"GitHub API request timed out for {url}. Not retrying.")
                return None # Fail this request
            except ConnectionError:
                # Could implement retries for connection errors if desired
                logger.error(f"GitHub API connection error for {url}. Not retrying.")
                return None # Fail this request
            except RequestException as e:
                logger.error(f"GitHub API request failed for {url}: {e}")
                if e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, content: {e.response.text[:200]}")
                    # Specific handling for common, non-retryable errors
                    if e.response.status_code in [404, 410, 401]: # Not Found, Gone, Unauthorized
                         return None # Don't retry these
                # For other request exceptions, we break the loop and return None
                return None
            except Exception as e:
                 # Catch any other unexpected error during the request/wait
                 logger.error(f"Unexpected error during GitHub request/wait for {url}: {e}", exc_info=True)
                 return None # Fail this request
            
    # Cache results for the same issue number within the same owner/repo
    @lru_cache(maxsize=2048) # Cache up to 2048 issue results
    def get_issue_data(self, owner: str, repo_name: str, issue_number: str) -> Optional[Dict[str, Any]]:
        """Fetches data for a specific issue, handling rate limits."""
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/issues/{issue_number}"
        logger.debug(f"Fetching GitHub issue: {owner}/{repo_name}#{issue_number}")
        # _make_request now returns None on failure after retries
        return self._make_request(api_url)

    def get_earliest_issue_open_timestamp(
        self,
        owner: str,
        repo_name: str,
        issue_ids: List[str]
    ) -> Optional[int]:
        """
        Gets the earliest 'created_at' timestamp (Unix epoch seconds) for a list of issue IDs.
        Waits and retries on rate limits.
        """
        earliest_timestamp: Optional[int] = None

        for issue_id in issue_ids:
            if not issue_id.isdigit():
                logger.warning(f"Invalid issue ID format skipped: {issue_id}")
                continue

            # get_issue_data now handles retries/waits internally
            issue_data = self.get_issue_data(owner, repo_name, issue_id)

            if issue_data and 'created_at' in issue_data:
                created_at_str = issue_data['created_at']
                try:
                    dt_obj = dateutil.parser.isoparse(created_at_str)
                    timestamp = int(dt_obj.timestamp())
                    if earliest_timestamp is None or timestamp < earliest_timestamp:
                        earliest_timestamp = timestamp
                except (ValueError, TypeError) as date_err:
                    logger.error(f"Error parsing date '{created_at_str}' for issue #{issue_id}: {date_err}")
            elif issue_data is None:
                 # Fetch failed after retries, log it but continue if possible
                 logger.error(f"Failed to fetch data for issue {owner}/{repo_name}#{issue_id} after retries/wait.")
                 # If one issue fails, should we stop? For now, let's try the others.

        if earliest_timestamp is not None:
            logger.debug(f"Found earliest issue open timestamp {earliest_timestamp} for issues {issue_ids} in {owner}/{repo_name}")
        else:
            logger.debug(f"No valid open date found for issues {issue_ids} in {owner}/{repo_name}")

        return earliest_timestamp


def extract_issue_ids(message: Optional[str]) -> List[str]:
    """Extracts unique issue IDs (digits only) from a commit message."""
    if not message:
        return []
    # Find all occurrences like #123, #45 etc.
    ids = ISSUE_ID_REGEX.findall(message)
    return sorted(list(set(ids)), key=int) # Return unique IDs sorted numerically