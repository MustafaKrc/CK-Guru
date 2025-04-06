import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import MagicMock # For mock_celery_send_task

from shared.db.models import Repository # Import the actual model
from backend.app.schemas import RepositoryRead, TaskResponse # Import schemas for comparison

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio

# Helper function to create a repo directly in the test DB for setup
async def create_test_repo(db: AsyncSession, name: str, url: str) -> Repository:
    repo = Repository(name=name, git_url=url)
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo

# === Test POST /repositories/ ===

async def test_create_repository_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test successful repository creation."""
    git_url = "https://github.com/test/create-success.git"
    response = await test_client.post("/api/v1/repositories/", json={"git_url": git_url})

    assert response.status_code == 201
    data = response.json()
    assert data["git_url"] == git_url
    assert data["name"] == "create-success" # Check extracted name
    assert "id" in data
    repo_id = data["id"]

    # Verify in DB
    stmt = select(Repository).where(Repository.id == repo_id)
    result = await db_session.execute(stmt)
    db_repo = result.scalar_one_or_none()
    assert db_repo is not None
    assert db_repo.git_url == git_url
    assert db_repo.name == "create-success"

async def test_create_repository_duplicate_url(test_client: AsyncClient, db_session: AsyncSession):
    """Test creating a repository with a duplicate Git URL."""
    git_url = "https://github.com/test/duplicate-url.git"
    # Create the first one directly
    await create_test_repo(db_session, "duplicate-1", git_url)

    # Attempt to create the second one via API
    response = await test_client.post("/api/v1/repositories/", json={"git_url": git_url})

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert f"'{git_url}' already exists" in data["detail"]

async def test_create_repository_invalid_url(test_client: AsyncClient):
    """Test creating a repository with an invalid Git URL."""
    response = await test_client.post("/api/v1/repositories/", json={"git_url": "not-a-valid-url"})
    assert response.status_code == 422 # Pydantic validation error

# === Test GET /repositories/ ===

async def test_read_repositories_empty(test_client: AsyncClient):
    """Test reading repositories when none exist."""
    response = await test_client.get("/api/v1/repositories/")
    assert response.status_code == 200
    assert response.json() == []

async def test_read_repositories_with_data(test_client: AsyncClient, db_session: AsyncSession):
    """Test reading repositories when some exist."""
    repo1 = await create_test_repo(db_session, "repo-get-1", "https://github.com/test/get-1.git")
    repo2 = await create_test_repo(db_session, "repo-get-2", "https://github.com/test/get-2.git")

    response = await test_client.get("/api/v1/repositories/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Check data - response should be ordered by created_at desc (newest first)
    # Convert response dicts to RepositoryRead for easier comparison if needed
    # Or compare specific fields
    ids_in_response = {item['id'] for item in data}
    assert ids_in_response == {repo1.id, repo2.id}
    # Example check on one item's structure
    assert data[0]['name'] == repo2.name # Assuming repo2 was created last
    assert data[0]['git_url'] == repo2.git_url

# === Test GET /repositories/{repo_id} ===

async def test_read_repository_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test reading a specific repository successfully."""
    repo = await create_test_repo(db_session, "repo-read-one", "https://github.com/test/read-one.git")

    response = await test_client.get(f"/api/v1/repositories/{repo.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo.id
    assert data["name"] == repo.name
    assert data["git_url"] == repo.git_url

async def test_read_repository_not_found(test_client: AsyncClient):
    """Test reading a repository that does not exist."""
    response = await test_client.get("/api/v1/repositories/99999")
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]

# === Test PUT /repositories/{repo_id} ===

async def test_update_repository_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test updating a repository successfully."""
    repo = await create_test_repo(db_session, "repo-update", "https://github.com/test/update.git")
    update_data = {"name": "updated-name", "git_url": "https://github.com/test/updated.git"}

    response = await test_client.put(f"/api/v1/repositories/{repo.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo.id
    assert data["name"] == update_data["name"]
    assert data["git_url"] == update_data["git_url"]

    # Verify in DB
    await db_session.refresh(repo) # Refresh the original object
    assert repo.name == update_data["name"]
    assert repo.git_url == update_data["git_url"]

async def test_update_repository_partial_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test partially updating a repository (only name)."""
    original_url = "https://github.com/test/partial-update.git"
    repo = await create_test_repo(db_session, "repo-partial-update", original_url)
    update_data = {"name": "updated-partial-name"}

    response = await test_client.put(f"/api/v1/repositories/{repo.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo.id
    assert data["name"] == update_data["name"]
    assert data["git_url"] == original_url # URL should not change

    # Verify in DB
    await db_session.refresh(repo)
    assert repo.name == update_data["name"]
    assert repo.git_url == original_url

async def test_update_repository_not_found(test_client: AsyncClient):
    """Test updating a repository that does not exist."""
    update_data = {"name": "updated-name"}
    response = await test_client.put("/api/v1/repositories/99999", json=update_data)
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]

async def test_update_repository_invalid_input(test_client: AsyncClient, db_session: AsyncSession):
    """Test updating a repository with invalid input data."""
    repo = await create_test_repo(db_session, "repo-invalid-update", "https://github.com/test/invalid-update.git")
    update_data = {"git_url": "not-a-url"} # Invalid URL
    response = await test_client.put(f"/api/v1/repositories/{repo.id}", json=update_data)
    assert response.status_code == 422

# === Test DELETE /repositories/{repo_id} ===

async def test_delete_repository_success(test_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a repository successfully."""
    repo = await create_test_repo(db_session, "repo-delete", "https://github.com/test/delete.git")
    repo_id = repo.id

    response = await test_client.delete(f"/api/v1/repositories/{repo_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo_id
    assert data["name"] == repo.name # API returns the deleted object

    # Verify in DB
    stmt = select(Repository).where(Repository.id == repo_id)
    result = await db_session.execute(stmt)
    db_repo = result.scalar_one_or_none()
    assert db_repo is None # Should be deleted

async def test_delete_repository_not_found(test_client: AsyncClient):
    """Test deleting a repository that does not exist."""
    response = await test_client.delete("/api/v1/repositories/99999")
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]

# === Test POST /repositories/{repo_id}/ingest ===

async def test_trigger_ingest_task_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_celery_send_task: MagicMock # Inject the mock fixture
):
    """Test successfully triggering the ingestion task."""
    repo = await create_test_repo(db_session, "repo-ingest", "https://github.com/test/ingest.git")

    response = await test_client.post(f"/api/v1/repositories/{repo.id}/ingest")

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["task_id"] == "mock_task_id_12345" # Check against mock return value
    assert "message" in data

    # Verify Celery task was called correctly
    mock_celery_send_task.assert_called_once()
    call_args, call_kwargs = mock_celery_send_task.call_args
    assert call_args[0] == "tasks.ingest_repository" # Task name
    assert call_args[1] == [repo.id, repo.git_url] # Positional args list
    assert call_kwargs.get("queue") == "ingestion"

async def test_trigger_ingest_task_repo_not_found(
    test_client: AsyncClient,
    mock_celery_send_task: MagicMock
):
    """Test triggering ingest task for a non-existent repository."""
    response = await test_client.post("/api/v1/repositories/99999/ingest")

    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]
    mock_celery_send_task.assert_not_called() # Ensure task was not sent