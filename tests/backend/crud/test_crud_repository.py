from unittest.mock import (  # Use AsyncMock for async functions
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

# Need SQLAlchemy core for comparisons if checking exact statements
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

# Import the module and specific functions/classes to test
from backend.app.crud import crud_repository
from shared.db.models import Repository  # Import the actual model
from shared.schemas.repository import RepositoryCreate, RepositoryUpdate

# --- Test _extract_repo_name ---


@pytest.mark.parametrize(
    "url, expected_name",
    [
        ("https://github.com/owner/repo.git", "repo"),
        ("https://github.com/owner/repo", "repo"),
        ("git@github.com:owner/repo-name.git", "repo-name"),
        ("https://gitlab.com/group/subgroup/project.git", "project"),
        ("https://github.com/owner/repo/", "repo"),  # Trailing slash
        ("https://github.com/owner/repo.with.dots.git", "repo.with.dots"),
        ("just-a-name", "just-a-name"),  # Less common case, but should handle
        ("https://github.com/", "unknown_repo"),  # Edge case
    ],
)
def test_extract_repo_name(url, expected_name):
    """Test the helper function to extract repo name from URL."""
    assert crud_repository._extract_repo_name(url) == expected_name


# --- Test CRUD Functions ---


@pytest.fixture
def mock_db_session():
    """Fixture to create a mock AsyncSession."""
    # Use AsyncMock for the session object itself and its methods
    session = AsyncMock(spec=AsyncSession)

    # Mock the execute method to return another AsyncMock
    execute_mock = AsyncMock()
    session.execute = execute_mock

    # Mock the result object returned by execute
    result_mock = MagicMock()  # Can be MagicMock as scalars/first are sync
    execute_mock.return_value = result_mock

    # Mock the methods typically called on the result
    scalars_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    scalars_mock.first.return_value = None  # Default to not found
    scalars_mock.all.return_value = []  # Default to empty list

    # Mock commit, add, refresh, delete
    session.commit = AsyncMock()
    session.add = MagicMock()  # add is synchronous
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    return session


@pytest.mark.asyncio
async def test_get_repository_found(mock_db_session):
    """Test get_repository when the repository is found."""
    repo_id = 1
    mock_repo = Repository(
        id=repo_id, name="test-repo", git_url="http://test.com/repo.git"
    )

    # Configure mock result
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = (
        mock_repo
    )

    result = await crud_repository.get_repository(mock_db_session, repo_id=repo_id)

    assert result == mock_repo
    # Optional: Assert execute was called (checking exact statement is fragile)
    assert mock_db_session.execute.call_count == 1
    call_args = mock_db_session.execute.call_args[0][0]  # Get the statement object
    assert isinstance(call_args, sa.sql.Select)  # Check it's a select statement


@pytest.mark.asyncio
async def test_get_repository_not_found(mock_db_session):
    """Test get_repository when the repository is not found."""
    repo_id = 99
    # Default mock setup returns None, so no extra config needed
    result = await crud_repository.get_repository(mock_db_session, repo_id=repo_id)
    assert result is None
    assert mock_db_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_repository_by_git_url_found(mock_db_session):
    """Test get_repository_by_git_url when found."""
    git_url = "http://test.com/repo.git"
    mock_repo = Repository(id=1, name="test-repo", git_url=git_url)
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = (
        mock_repo
    )

    result = await crud_repository.get_repository_by_git_url(
        mock_db_session, git_url=git_url
    )

    assert result == mock_repo
    assert mock_db_session.execute.call_count == 1
    # Optional: Verify the where clause of the statement if desired


@pytest.mark.asyncio
async def test_get_repository_by_git_url_not_found(mock_db_session):
    """Test get_repository_by_git_url when not found."""
    git_url = "http://test.com/notfound.git"
    result = await crud_repository.get_repository_by_git_url(
        mock_db_session, git_url=git_url
    )
    assert result is None
    assert mock_db_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_repositories(mock_db_session):
    """Test getting multiple repositories."""
    mock_repo1 = Repository(id=1, name="repo1", git_url="http://test.com/1.git")
    mock_repo2 = Repository(id=2, name="repo2", git_url="http://test.com/2.git")
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_repo1,
        mock_repo2,
    ]

    result = await crud_repository.get_repositories(mock_db_session, skip=0, limit=100)

    assert result == [mock_repo1, mock_repo2]
    assert mock_db_session.execute.call_count == 1
    call_args = mock_db_session.execute.call_args[0][0]  # Get the statement object
    assert isinstance(call_args, sa.sql.Select)
    # Optional: Check for offset/limit clauses if testing pagination rigorously


@pytest.mark.asyncio
async def test_get_repositories_empty(mock_db_session):
    """Test getting multiple repositories when none exist."""
    # Default mock setup returns [], so no extra config needed
    result = await crud_repository.get_repositories(mock_db_session, skip=0, limit=100)
    assert result == []
    assert mock_db_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_create_repository(mock_db_session):
    """Test creating a new repository."""
    repo_in = RepositoryCreate(git_url="https://github.com/test/new-repo.git")
    expected_name = "new-repo"  # From _extract_repo_name

    # The actual instance passed to add/refresh will be created inside the function
    # We only need to ensure the mocks are called correctly.

    # We don't mock the Repository() constructor directly here, we trust it works.
    # We expect the function to call add, commit, refresh on the session.

    created_repo = await crud_repository.create_repository(
        db=mock_db_session, obj_in=repo_in
    )

    # Assertions focus on the interaction with the session mock
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once()

    # Check the object that was added
    added_object = mock_db_session.add.call_args[0][0]
    assert isinstance(added_object, Repository)
    assert added_object.git_url == str(repo_in.git_url)  # Compare string form
    assert added_object.name == expected_name

    # Check the object that was refreshed (should be the same instance)
    refreshed_object = mock_db_session.refresh.call_args[0][0]
    assert refreshed_object is added_object

    # The function returns the object instance created internally
    assert created_repo is added_object


@pytest.mark.asyncio
async def test_update_repository(mock_db_session):
    """Test updating an existing repository."""
    db_repo = Repository(id=1, name="old-name", git_url="http://old.com/repo.git")
    repo_in = RepositoryUpdate(name="new-name", git_url="http://new.com/repo.git")

    # Simulate the update process
    updated_repo = await crud_repository.update_repository(
        db=mock_db_session, db_obj=db_repo, obj_in=repo_in
    )

    # Check that the original object was modified
    assert db_repo.name == "new-name"
    assert (
        str(db_repo.git_url) == "http://new.com/repo.git"
    )  # Compare string representation

    # Check session interactions
    mock_db_session.add.assert_called_once_with(db_repo)  # Add the modified object
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once_with(db_repo)

    # The function returns the modified db_obj
    assert updated_repo is db_repo


@pytest.mark.asyncio
async def test_update_repository_partial(mock_db_session):
    """Test partially updating an existing repository."""
    original_url = "http://old.com/repo.git"
    db_repo = Repository(id=1, name="old-name", git_url=original_url)
    repo_in = RepositoryUpdate(name="new-name-only")  # Only update name

    updated_repo = await crud_repository.update_repository(
        db=mock_db_session, db_obj=db_repo, obj_in=repo_in
    )

    assert db_repo.name == "new-name-only"
    assert db_repo.git_url == original_url  # URL should not have changed

    mock_db_session.add.assert_called_once_with(db_repo)
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once_with(db_repo)
    assert updated_repo is db_repo


@pytest.mark.asyncio
async def test_delete_repository_found(mock_db_session):
    """Test deleting a repository when it exists."""
    repo_id = 1
    # Need to mock get_repository behavior *within* delete_repository
    # Easiest is to assume delete_repository is called with the object already fetched
    # Alternatively, patch crud_repository.get_repository
    db_repo = Repository(
        id=repo_id, name="to-delete", git_url="http://delete.me/repo.git"
    )

    # Temporarily configure the mock session's get method if delete uses it
    # Or rely on the `get_repository` mock setup if delete calls it
    # Let's assume delete gets the object first somehow (common pattern)
    # We will mock the get *outside* this test if needed, or patch specifically

    # Patch crud_repository.get_repository just for this test
    with patch(
        "backend.app.crud.crud_repository.get_repository", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = db_repo

        deleted_repo = await crud_repository.delete_repository(
            db=mock_db_session, repo_id=repo_id
        )

        mock_get.assert_awaited_once_with(mock_db_session, repo_id)
        mock_db_session.delete.assert_awaited_once_with(db_repo)
        mock_db_session.commit.assert_awaited_once()
        assert deleted_repo is db_repo  # Returns the deleted object


@pytest.mark.asyncio
async def test_delete_repository_not_found(mock_db_session):
    """Test deleting a repository when it doesn't exist."""
    repo_id = 99
    # Patch crud_repository.get_repository to return None
    with patch(
        "backend.app.crud.crud_repository.get_repository", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        deleted_repo = await crud_repository.delete_repository(
            db=mock_db_session, repo_id=repo_id
        )

        mock_get.assert_awaited_once_with(mock_db_session, repo_id)
        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_called()
        assert deleted_repo is None  # Returns None when not found
