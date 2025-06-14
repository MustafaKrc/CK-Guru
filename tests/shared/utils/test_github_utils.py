import time
from typing import Optional
from unittest.mock import (
    ANY,  # ANY is useful for comparing headers loosely
    MagicMock,
    patch,
)

import pytest
import requests  # Import for exceptions and structures
from requests.exceptions import ConnectionError, RequestException, Timeout

# Import functions and classes to test
from shared.utils import github_utils
from shared.utils.github_utils import (
    GitHubAPIResponse,
    GitHubIssueFetcher,
    extract_issue_ids,
    extract_repo_owner_name,
)  # Import for type hinting and comparison

# --- Tests for extract_repo_owner_name ---


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/owner/repo.git", ("owner", "repo")),
        ("https://github.com/owner/repo", ("owner", "repo")),
        ("git@github.com:owner/repo.git", ("owner", "repo")),
        ("git@github.com:owner/repo", ("owner", "repo")),
        (
            "https://github.com/valid-owner/repo-with-hyphens.git",
            ("valid-owner", "repo-with-hyphens"),
        ),
        ("https://github.com/dots.owner/dots.repo.git", ("dots.owner", "dots.repo")),
        ("https://gitlab.com/owner/repo.git", None),  # Invalid domain
        ("https://github.com/owner", None),  # Missing repo
        ("invalid-url", None),
        ("", None),
    ],
)
def test_extract_repo_owner_name(url, expected):
    """Test extracting owner and repo name from various URL formats."""
    assert github_utils.extract_repo_owner_name(url) == expected


# --- Tests for extract_issue_ids ---


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Fixes #123", ["123"]),
        ("Addresses #45 and resolves #678", ["45", "678"]),
        ("Closes #9, see also issue #10", ["9", "10"]),
        ("Duplicate fix for #123", ["123"]),  # Should be unique
        ("Some message without issue numbers 123 45", []),
        ("Related to internal ticket TICKET-123", []),
        ("Message with # only", []),
        ("", []),
        (None, []),
    ],
)
def test_extract_issue_ids(message, expected):
    """Test extracting unique issue IDs from commit messages."""
    assert github_utils.extract_issue_ids(message) == expected


# --- Tests for GitHubIssueFetcher ---


# Mock the logger to avoid actual logging during tests
@pytest.fixture(autouse=True)
def mock_github_utils_logging():
    with patch("shared.utils.github_utils.logger", MagicMock()):
        yield


@pytest.fixture
def mock_requests_session_get():
    """Fixture to mock requests.Session.get"""
    with patch("requests.Session.get", autospec=True) as mock_get:
        yield mock_get


# Helper to create a mock response
def create_mock_response(
    status_code: int,
    json_data: Optional[dict] = None,
    headers: Optional[dict] = None,
    raise_for_status_exception: Optional[Exception] = None,
    text: Optional[str] = None,
):
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.headers = requests.structures.CaseInsensitiveDict(headers or {})
    mock_resp.text = text if text is not None else str(json_data or "")
    if raise_for_status_exception:
        mock_resp.raise_for_status.side_effect = raise_for_status_exception
    elif (
        status_code >= 400 and status_code != 403
    ):  # Simulate non-403 errors for raise_for_status
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
    return mock_resp


# -- GitHubIssueFetcher Initialization Tests --
def test_githubissuefetcher_init_with_token():
    """Test fetcher initialization with a token."""
    token = "test_token_123"
    fetcher = GitHubIssueFetcher(token=token)
    assert fetcher.token == token
    assert "Authorization" in fetcher.session.headers
    assert fetcher.session.headers["Authorization"] == f"token {token}"
    assert fetcher.session.headers["Accept"] == "application/vnd.github.v3+json"


def test_githubissuefetcher_init_without_token():
    """Test fetcher initialization without a token."""
    fetcher = GitHubIssueFetcher(token=None)
    assert fetcher.token is None
    assert "Authorization" not in fetcher.session.headers
    assert fetcher.session.headers["Accept"] == "application/vnd.github.v3+json"


# -- GitHubIssueFetcher._parse_rate_limit_headers Tests --
@pytest.mark.parametrize(
    "headers, expected_remaining, expected_reset",
    [
        (
            {"X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "1678886400"},
            50,
            1678886400,
        ),
        ({"X-RateLimit-Remaining": "0"}, 0, None),
        ({"X-RateLimit-Reset": "1678886400"}, None, 1678886400),
        ({}, None, None),
        ({"X-RateLimit-Remaining": "abc", "X-RateLimit-Reset": "xyz"}, None, None),
        (
            {"x-ratelimit-remaining": "10", "x-ratelimit-reset": "1678886401"},
            10,
            1678886401,
        ),  # Case-insensitive
    ],
)
def test_parse_rate_limit_headers(headers, expected_remaining, expected_reset):
    """Test parsing of rate limit headers."""
    fetcher = GitHubIssueFetcher(token=None)  # Doesn't matter for this method
    remaining, reset = fetcher._parse_rate_limit_headers(
        requests.structures.CaseInsensitiveDict(headers)
    )
    assert remaining == expected_remaining
    assert reset == expected_reset


# -- GitHubIssueFetcher._make_request Tests --
def test_make_request_success_200_ok(mock_requests_session_get):
    """Test successful 200 OK response."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/test"
    mock_json = {"id": 1, "name": "test"}
    mock_headers = {
        "ETag": "etag123",
        "X-RateLimit-Remaining": "99",
        "X-RateLimit-Reset": "1700000000",
    }
    mock_requests_session_get.return_value = create_mock_response(
        200, json_data=mock_json, headers=mock_headers
    )

    response = fetcher._make_request(url)

    assert response == GitHubAPIResponse(
        status_code=200,
        etag="etag123",
        json_data=mock_json,
        rate_limit_remaining=99,
        rate_limit_reset=1700000000,
        error_message=None,
    )
    # Check only args *after* self
    mock_requests_session_get.assert_called_once()  # Check it was called once
    call_args, call_kwargs = mock_requests_session_get.call_args
    assert call_args[1] == url  # url is the second positional arg after self
    assert call_kwargs["headers"] == ANY
    assert call_kwargs["timeout"] == 20
    call_headers = mock_requests_session_get.call_args.kwargs["headers"]
    assert "If-None-Match" not in call_headers  # No ETag provided in request


def test_make_request_success_with_request_etag(mock_requests_session_get):
    """Test successful 200 OK response when passing an ETag."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/test"
    request_etag = "etag_request"
    mock_json = {"id": 1, "name": "test_updated"}
    mock_headers = {
        "ETag": "etag_response",
        "X-RateLimit-Remaining": "98",
        "X-RateLimit-Reset": "1700000001",
    }
    mock_requests_session_get.return_value = create_mock_response(
        200, json_data=mock_json, headers=mock_headers
    )

    response = fetcher._make_request(url, etag=request_etag)

    assert response.status_code == 200
    assert response.etag == "etag_response"
    assert response.json_data == mock_json
    # Check only args *after* self
    mock_requests_session_get.assert_called_once()
    call_args, call_kwargs = mock_requests_session_get.call_args
    assert call_args[1] == url
    # Check specific header for If-None-Match
    assert call_kwargs["headers"]["If-None-Match"] == request_etag
    assert call_kwargs["timeout"] == 20
    call_headers = mock_requests_session_get.call_args.kwargs["headers"]
    assert call_headers["If-None-Match"] == request_etag


def test_make_request_not_modified_304(mock_requests_session_get):
    """Test 304 Not Modified response."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/test"
    request_etag = "etag123"
    mock_headers = {
        "ETag": "etag123",
        "X-RateLimit-Remaining": "97",
        "X-RateLimit-Reset": "1700000002",
    }  # ETag can be same or different
    mock_requests_session_get.return_value = create_mock_response(
        304, headers=mock_headers
    )

    response = fetcher._make_request(url, etag=request_etag)

    assert response == GitHubAPIResponse(
        status_code=304,
        etag="etag123",
        json_data=None,
        rate_limit_remaining=97,
        rate_limit_reset=1700000002,
        error_message=None,
    )
    # Check only args *after* self
    mock_requests_session_get.assert_called_once()
    call_args, call_kwargs = mock_requests_session_get.call_args
    assert call_args[1] == url
    assert call_kwargs["headers"]["If-None-Match"] == request_etag
    assert call_kwargs["timeout"] == 20
    call_headers = mock_requests_session_get.call_args.kwargs["headers"]
    assert call_headers["If-None-Match"] == request_etag


@patch("time.sleep", return_value=None)  # Mock time.sleep
def test_make_request_rate_limit_hit_and_retry(mock_sleep, mock_requests_session_get):
    """Test hitting rate limit (403) and successfully retrying."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/test"
    reset_time = int(time.time()) + 10  # Simulate reset time 10s in future

    # First response: 403 Rate Limit Hit
    mock_response_403 = create_mock_response(
        403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_time)},
        # raise_for_status_exception=requests.exceptions.HTTPError(response=MagicMock(status_code=403)) # raise_for_status isn't called for 403
    )
    # Second response: 200 OK after wait
    mock_response_200 = create_mock_response(
        200,
        json_data={"id": 2},
        headers={
            "ETag": "etag456",
            "X-RateLimit-Remaining": "5000",
            "X-RateLimit-Reset": str(reset_time + 3600),
        },
    )

    mock_requests_session_get.side_effect = [mock_response_403, mock_response_200]

    response = fetcher._make_request(url)

    # Assert the final successful response
    assert response.status_code == 200
    assert response.json_data == {"id": 2}
    assert response.etag == "etag456"

    # Assert sleep was called (approx time + buffer)
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] >= 10  # Check if sleep duration is approx correct
    assert (
        mock_sleep.call_args[0][0] <= 10 + github_utils.RATE_LIMIT_BUFFER_SECONDS + 2
    )  # Allow buffer + slight timing diff

    # Assert session.get was called twice
    assert mock_requests_session_get.call_count == 2


@patch("time.sleep", return_value=None)  # Mock time.sleep
def test_make_request_rate_limit_max_retries(mock_sleep, mock_requests_session_get):
    """Test hitting rate limit and exceeding max retries."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/test"
    reset_time = int(time.time()) + 10

    # Create mock 403 responses for all retries + initial call
    mock_response_403 = create_mock_response(
        403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_time)},
    )
    # Make it return 403 enough times to exceed retries
    mock_requests_session_get.side_effect = [mock_response_403] * (
        github_utils.MAX_RATE_LIMIT_RETRIES + 1
    )

    response = fetcher._make_request(url)

    # Assert the final response is the 403 error
    assert response.status_code == 403
    assert response.json_data is None
    assert "max retries" in response.error_message
    assert response.rate_limit_remaining == 0
    assert response.rate_limit_reset == reset_time

    # Assert sleep was called MAX_RATE_LIMIT_RETRIES times
    assert mock_sleep.call_count == github_utils.MAX_RATE_LIMIT_RETRIES
    # Assert session.get was called MAX_RATE_LIMIT_RETRIES + 1 times
    assert (
        mock_requests_session_get.call_count == github_utils.MAX_RATE_LIMIT_RETRIES + 1
    )


def test_make_request_not_found_404(mock_requests_session_get):
    """Test 404 Not Found response."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/nonexistent"
    mock_response_404 = create_mock_response(
        404,
        json_data={"message": "Not Found"},
        headers={"X-RateLimit-Remaining": "96", "X-RateLimit-Reset": "1700000003"},
        text='{"message": "Not Found"}',
    )
    mock_requests_session_get.return_value = mock_response_404

    response = fetcher._make_request(url)

    assert response.status_code == 404
    assert response.json_data is None  # Should not return JSON on error
    assert "Status 404" in response.error_message
    assert "Not Found" in response.error_message
    assert response.rate_limit_remaining == 96
    assert response.rate_limit_reset == 1700000003


def test_make_request_timeout_error(mock_requests_session_get):
    """Test handling of requests.exceptions.Timeout."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/timeout"
    mock_requests_session_get.side_effect = Timeout("Request timed out")

    response = fetcher._make_request(url)

    assert response.status_code == 408
    assert response.json_data is None
    assert "timed out" in response.error_message
    assert response.rate_limit_remaining is None  # Not available on timeout
    assert response.rate_limit_reset is None


def test_make_request_connection_error(mock_requests_session_get):
    """Test handling of requests.exceptions.ConnectionError."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/connection_error"
    mock_requests_session_get.side_effect = ConnectionError("Could not connect")

    response = fetcher._make_request(url)

    assert response.status_code == 503  # Mapped to 503 Service Unavailable
    assert response.json_data is None
    assert "connection error" in response.error_message
    assert response.rate_limit_remaining is None
    assert response.rate_limit_reset is None


def test_make_request_other_request_exception(mock_requests_session_get):
    """Test handling of other RequestExceptions (e.g., 500)."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/server_error"
    # Create a mock response for the exception context
    error_response = create_mock_response(
        500,
        json_data={"message": "Internal Server Error"},
        text='{"message": "Internal Server Error"}',  # <<< Add text
    )
    mock_requests_session_get.side_effect = RequestException(response=error_response)
    mock_requests_session_get.side_effect = RequestException(response=error_response)

    response = fetcher._make_request(url)

    assert response.status_code == 500
    assert response.json_data is None
    assert "Status 500" in response.error_message
    assert "Internal Server Error" in response.error_message


def test_make_request_unexpected_exception(mock_requests_session_get):
    """Test handling of unexpected non-requests exceptions."""
    fetcher = GitHubIssueFetcher("fake_token")
    url = "https://api.github.com/unexpected"
    mock_requests_session_get.side_effect = ValueError(
        "Something went wrong unexpectedly"
    )

    response = fetcher._make_request(url)

    assert response.status_code == 500
    assert response.json_data is None
    assert "Unexpected error" in response.error_message
    assert (
        "Something went wrong unexpectedly" in response.error_message
    )  # Check for the specific message


# -- GitHubIssueFetcher.get_issue_data Tests --
@patch.object(
    GitHubIssueFetcher, "_make_request", autospec=True
)  # Mock the internal method
def test_get_issue_data_calls_make_request(mock_internal_make_request):
    """Test that get_issue_data correctly calls _make_request."""
    fetcher = GitHubIssueFetcher("fake_token")
    owner = "test_owner"
    repo_name = "test_repo"
    issue_number = "42"
    etag = "etag789"

    # Define the expected return value from the mocked _make_request
    expected_api_response = GitHubAPIResponse(
        status_code=200, json_data={"issue": "data"}, etag="new_etag"
    )
    mock_internal_make_request.return_value = expected_api_response

    result = fetcher.get_issue_data(owner, repo_name, issue_number, current_etag=etag)

    # Assert the result is what the mocked method returned
    assert result == expected_api_response

    # Assert _make_request was called correctly
    expected_url = (
        f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}"
    )
    mock_internal_make_request.assert_called_once_with(fetcher, expected_url, etag=etag)
