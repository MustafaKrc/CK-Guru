# shared/repositories/ml_model_type_definition_repository.py
import logging
from typing import List, Optional, Dict, Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.db.models import MLModelTypeDefinitionDB
from shared.schemas.ml_model_type_definition import MLModelTypeDefinitionCreate, MLModelTypeDefinitionUpdate
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)

class MLModelTypeDefinitionRepository(BaseRepository):

    def get_by_type_name(self, type_name: str) -> Optional[MLModelTypeDefinitionDB]:
        with self._session_scope() as session:
            return session.execute(
                select(MLModelTypeDefinitionDB).filter(MLModelTypeDefinitionDB.type_name == type_name)
            ).scalar_one_or_none()

    def get_all_enabled(self, skip: int = 0, limit: int = 100) -> Sequence[MLModelTypeDefinitionDB]:
        with self._session_scope() as session:
            return session.execute(
                select(MLModelTypeDefinitionDB)
                .filter(MLModelTypeDefinitionDB.is_enabled == True)
                .order_by(MLModelTypeDefinitionDB.display_name)
                .offset(skip)
                .limit(limit)
            ).scalars().all()

    def upsert_model_type_definitions(self, definitions: List[Dict[str, Any]], worker_identifier: str):
        """
        Upserts ML model type definitions into the database.
        Marks definitions previously managed by this worker but no longer discovered as not implemented.
        """
        if not definitions and not worker_identifier: # Allow empty definitions if worker_identifier is provided for cleanup
            logger.warning("Upsert called with no definitions and no worker_identifier. Skipping DB update.")
            return

        discovered_type_names = {d["type_name"] for d in definitions}

        with self._session_scope() as session:
            if definitions:
                logger.info(f"Upserting {len(definitions)} model type definitions from {worker_identifier} into DB...")
                
                insert_stmt = pg_insert(MLModelTypeDefinitionDB).values(definitions)
                
                update_columns = {
                    col.name: getattr(insert_stmt.excluded, col.name)
                    for col in MLModelTypeDefinitionDB.__table__.columns
                    if col.name != "type_name" # Exclude PK
                }
                # Always update last_updated_by and ensure is_enabled is set to True for discovered types
                update_columns["last_updated_by"] = worker_identifier
                update_columns["is_enabled"] = True # Assume discovered types should be enabled by default
                                                    # Admin can disable them manually later via UI/API if needed.

                upsert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["type_name"],
                    set_=update_columns,
                )
                session.execute(upsert_stmt)
                logger.info(f"{len(definitions)} model types upserted/updated.")

            # Mark types previously updated by this worker but not in the current discovery set as disabled.
            # This helps remove/disable types if a worker no longer supports them.
            # We only disable, not delete, to preserve any manual configurations.
            logger.info(f"Marking model types as disabled if previously managed by '{worker_identifier}' and not in current discovery set...")
            update_stmt_disable_old = (
                update(MLModelTypeDefinitionDB)
                .where(
                    MLModelTypeDefinitionDB.last_updated_by == worker_identifier,
                    ~MLModelTypeDefinitionDB.type_name.in_(discovered_type_names)
                )
                .values(is_enabled=False, last_updated_by=worker_identifier) # Mark as disabled and update who did it
                .execution_options(synchronize_session=False)
            )
            result = session.execute(update_stmt_disable_old)
            if result.rowcount > 0:
                logger.info(f"Marked {result.rowcount} old model types as disabled for worker '{worker_identifier}'.")
            
            session.commit()