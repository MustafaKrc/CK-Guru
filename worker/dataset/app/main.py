# worker/dataset/app/main.py
import json
import logging
from typing import List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert # Use specific dialect for UPSERT

from shared.db.models import CleaningRuleDefinitionDB
from shared.db_session import get_sync_db_session
from shared.core.config import settings
from shared.cleaning_rules import discover_rules, WORKER_RULE_REGISTRY, RuleDefinition
from shared.celery_config.app import create_celery_app

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

WORKER_IDENTIFIER = "dataset-worker" # Define an identifier for this worker type

def update_rule_registry_in_db():
    """Discovers rules and UPSERTs their definitions into the database."""
    logger.info("Updating cleaning rule registry in database...")
    discovered_rule_names = set(WORKER_RULE_REGISTRY.keys())
    definitions_to_upsert: List[Dict[str, Any]] = []

    for rule_name, rule_cls in WORKER_RULE_REGISTRY.items():
        try:
            instance = rule_cls()
            definition: RuleDefinition = instance.get_definition()
            # Prepare data for DB model (convert params list to JSON-compatible dict list)
            db_data = definition.model_dump(mode='json') # Pydantic v2
            db_data['is_implemented'] = True # Mark as implemented by this worker
            db_data['last_updated_by'] = WORKER_IDENTIFIER
            definitions_to_upsert.append(db_data)
        except Exception as e:
            logger.error(f"Failed to get definition for rule '{rule_name}': {e}", exc_info=True)

    if not definitions_to_upsert:
        logger.warning("No rule definitions discovered or generated. DB registry not updated.")
        return

    try:
        with get_sync_db_session() as session:
            logger.info(f"Upserting {len(definitions_to_upsert)} rule definitions into DB...")
            # --- UPSERT Logic (PostgreSQL example) ---
            insert_stmt = pg_insert(CleaningRuleDefinitionDB).values(definitions_to_upsert)
            # Define columns to update on conflict
            update_columns = {
                col.name: col
                for col in insert_stmt.excluded # Reference inserted values
                if col.name not in ['name'] # Don't update the primary key
            }
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['name'], # Conflict target (the primary key)
                set_=update_columns # Values to update if conflict occurs
            )
            session.execute(upsert_stmt)

            # --- Mark missing rules as not implemented ---
            logger.info("Marking rules not found in worker as 'not implemented'...")
            update_stmt = (
                update(CleaningRuleDefinitionDB)
                .where(
                    CleaningRuleDefinitionDB.is_implemented == True,
                    CleaningRuleDefinitionDB.last_updated_by == WORKER_IDENTIFIER, # Only affect rules last updated by this worker type?
                    ~CleaningRuleDefinitionDB.name.in_(discovered_rule_names) # Use ~ for NOT IN
                )
                .values(is_implemented=False, last_updated_by=WORKER_IDENTIFIER)
            )
            result = session.execute(update_stmt)
            logger.info(f"Marked {result.rowcount} rules as not implemented.")

            session.commit() # Commit both upsert and update
            logger.info("Rule registry DB update complete.")

    except Exception as e:
        logger.error(f"Failed to update rule registry in DB: {e}", exc_info=True)
        # Should this prevent worker startup? Potentially.

# --- Worker Initialization ---
logger.info("Dataset worker starting up...")
discover_rules(module_path="services.cleaning_rules") # Discover rules first
update_rule_registry_in_db() # Update DB with discovered rules

# Create Celery app instance
celery_app = create_celery_app(
    main_name="dataset_worker",
    include_tasks=["app.tasks"]
)
logger.info("Celery app created for dataset worker.")