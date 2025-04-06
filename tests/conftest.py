import os
from typing import AsyncGenerator, Generator # Use AsyncGenerator
from pathlib import Path
from unittest.mock import MagicMock
from pathlib import Path


import pytest
import pytest_asyncio # Use the specific import for async fixtures
from httpx import AsyncClient, patch, ASGITransport
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool # Use NullPool for test DB engine

# Project imports
from backend.app.main import app # Import your FastAPI app
from shared.db.base_class import Base # Import Base for metadata
from shared.db_session import get_async_db_session # Import the original dependency
from shared.core.config import settings # Import settings

# --- Test Database Configuration ---
# Ensure you have a separate TEST database configured (e.g., via environment vars)
# Load environment variables from .env file in the root folder

# Find the root directory (assuming conftest.py is in the tests folder)
root_dir = Path(__file__).parent.parent  # Go up one level from tests to project root
load_dotenv(root_dir / ".env")  # Load .env from project root

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit("TEST_DATABASE_URL environment variable is not set. Skipping integration tests.", returncode=1)

# Create SQLAlchemy engine for testing (use NullPool to avoid hanging connections)
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)

# Create sessionmaker for testing
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False
)

# --- Fixture to manage database schema (Optional but Recommended) ---
# This fixture ensures the database schema is created before tests run
# and dropped afterwards. It depends on Alembic setup.
@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """
    Applies Alembic migrations at the start of the test session and
    downgrades/cleans up afterwards. Requires Alembic to be configured
    to read the TEST_DATABASE_URL.
    """
    from alembic.config import Config
    from alembic import command
    import asyncio

    tests_folder_path = Path(__file__).parent # Path to this conftest.py file
    #backend_tests_dir = conftest_file_path / "backend" # Path to tests/backend
    backend_root_dir = tests_folder_path.parent / "backend" # Path to backend/
    alembic_ini_path = backend_root_dir / "alembic.ini" # Expected: backend/alembic.ini

    if not alembic_ini_path.is_file():
         pytest.fail(f"Alembic configuration file not found at expected path: {alembic_ini_path}")

    print(f"\nApplying migrations using config: {alembic_ini_path}")
    print(f"Applying migrations to test database: {TEST_DATABASE_URL}...")

    # Pass the absolute path string to Config
    alembic_cfg = Config(str(alembic_ini_path)) # <-- Use the calculated path string

    # Override the sqlalchemy.url (make sure TEST_DATABASE_URL is correct)
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Ensure env.py can find shared models by adding project root temporarily if needed
    # project_root = backend_root_dir.parent
    # original_path = sys.path[:]
    # if str(project_root) not in sys.path:
    #      sys.path.insert(0, str(project_root))

    try:
        command.upgrade(alembic_cfg, "head")
        print("Migrations applied.")
        yield # Tests run here
        print("\nDropping all tables from test database...")

        # --- Drop all tables for cleanup ---
        async def drop_all_tables():
             async with test_engine.begin() as conn:
                 # We need Base.metadata which should contain all tables
                 # Ensure all models are imported somewhere Base knows about them
                 # Usually done by importing models in env.py or base_class/__init__
                 await conn.run_sync(Base.metadata.drop_all)

        asyncio.run(drop_all_tables())
        print("Test database tables dropped.")

    except Exception as e:
        pytest.fail(f"Alembic migration/cleanup failed: {e}\nUsing config: {alembic_ini_path}\nTarget DB: {TEST_DATABASE_URL}", pytrace=True)
    # finally:
        # Restore sys.path if modified
        # sys.path = original_path


# --- Fixture for providing a test database session ---
@pytest_asyncio.fixture(scope="function") # Function scope for isolation
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean database session for each test function.
    """
    async with TestingSessionLocal() as session:
        yield session
        # You might uncomment rollback if tests modify data and need cleanup
        # await session.rollback() # Rollback any changes made during the test


# --- Fixture for overriding the main DB session dependency ---
@pytest.fixture(scope="function") # Depends on db_session fixture
def override_get_db(db_session: AsyncSession):
    """
    Overrides the `get_async_db_session` dependency in the FastAPI app
    to yield the test database session.
    """
    async def _override_get_db():
        yield db_session

    # Apply the override
    app.dependency_overrides[get_async_db_session] = _override_get_db
    yield # Test runs with the override
    # Clean up override after test finishes
    del app.dependency_overrides[get_async_db_session]


# --- Fixture for the Test Client ---
@pytest_asyncio.fixture(scope="function")
async def test_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an asynchronous test client (httpx.AsyncClient)
    configured to talk to the test instance of the FastAPI application.
    Relies on the override_get_db fixture.
    """
    # Explicitly specify the anyio backend and pass the app
    async with AsyncClient(
        transport=ASGITransport(app=app), # Use ASGITransport explicitly
        base_url="http://testserver"
    ) as client:
        yield client

# --- Fixture for Mocking Celery ---
@pytest.fixture(scope="function")
def mock_celery_send_task():
    """Mocks the celery_app.send_task method."""
    # Adjust the path ('backend.app.api.v1.endpoints.repositories.backend_celery_app')
    # based on where backend_celery_app is *imported* in the endpoint file.
    # Or mock it where it's defined if easier: 'backend.app.core.celery_app.backend_celery_app'
    # Let's try mocking where it's defined.
    with patch('backend.app.core.celery_app.backend_celery_app.send_task') as mock_send:
        # Configure mock to return a mock task object with an ID
        mock_task = MagicMock()
        mock_task.id = "mock_task_id_12345"
        mock_send.return_value = mock_task
        yield mock_send # Provide the mock object to the test if needed