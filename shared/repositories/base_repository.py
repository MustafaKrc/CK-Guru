# shared/repositories/base_repository.py
import logging
# Import Iterator or Generator from typing
from typing import Callable, TypeVar, Generic, Iterator # Or use Generator
from sqlalchemy.orm import Session
from contextlib import contextmanager

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    """Base class for data repositories."""

    def __init__(self, session_factory: Callable[..., Session]):
        self.session_factory = session_factory
        logger.debug(f"{self.__class__.__name__} initialized.")

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Provide a transactional scope around a series of operations."""
        session = self.session_factory()
        logger.debug(f"Session {id(session)} created for {self.__class__.__name__}.")
        try:
            yield session # Yield the session object
            # Commits are handled outside by default
        except Exception as e:
            logger.error(f"Session {id(session)} rollback initiated in {self.__class__.__name__} due to: {e}", exc_info=False) # Log exception type
            session.rollback()
            raise
        finally:
            logger.debug(f"Closing session {id(session)} in {self.__class__.__name__}.")
            session.close()

