# worker/dataset/app/main.py

import logging
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import List, Dict, Any

from shared.db.models import CleaningRuleDefinitionDB
from shared.db_session import get_sync_db_session
from shared.core.config import settings
# Update import path for rule discovery
from services.cleaning_rules.base import discover_rules, WORKER_RULE_REGISTRY, RuleDefinition
from shared.celery_config.app import create_celery_app

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

WORKER_IDENTIFIER = "dataset-worker"

def update_rule_registry_in_db(registry_snapshot: Dict[str, Any]):
    """UPSERTs rule definitions into the database using a snapshot of the registry."""
    logger.info("Updating cleaning rule registry in database...")
    discovered_rule_names = set(registry_snapshot.keys())
    definitions_to_upsert: List[Dict[str, Any]] = []

    for rule_name, rule_cls in registry_snapshot.items():
        try:
            instance = rule_cls()
            definition: RuleDefinition = instance.get_definition()
            db_data = definition.model_dump(mode='json')
            db_data['is_implemented'] = True
            db_data['last_updated_by'] = WORKER_IDENTIFIER
            definitions_to_upsert.append(db_data)
        except Exception as e:
            logger.error(f"Failed to get definition for rule '{rule_name}': {e}", exc_info=True)

    if not definitions_to_upsert and not discovered_rule_names: # Only skip if truly nothing to do
        logger.warning("No rule definitions discovered. DB registry not updated.")
        return

    try:
        with get_sync_db_session() as session:
            # --- UPSERT Logic ---
            if definitions_to_upsert:
                 logger.info(f"Upserting {len(definitions_to_upsert)} rule definitions into DB...")
                 insert_stmt = pg_insert(CleaningRuleDefinitionDB).values(definitions_to_upsert)
                 update_columns = {
                     col.name: col for col in insert_stmt.excluded
                     if col.name not in ['name']
                 }
                 upsert_stmt = insert_stmt.on_conflict_do_update(
                     index_elements=['name'], set_=update_columns
                 )
                 session.execute(upsert_stmt)

            # --- Mark missing rules as not implemented ---
            logger.info(f"Marking rules not implemented by {WORKER_IDENTIFIER} if not discovered...")
            update_stmt = (
                update(CleaningRuleDefinitionDB)
                .where(
                    # Only mark rules as not implemented if they were previously known by *this* worker type
                    CleaningRuleDefinitionDB.last_updated_by == WORKER_IDENTIFIER,
                    # AND the rule name is NOT in the set we just discovered
                    ~CleaningRuleDefinitionDB.name.in_(discovered_rule_names)
                )
                .values(is_implemented=False, last_updated_by=WORKER_IDENTIFIER)
                .execution_options(synchronize_session=False) # Use recommended option for bulk updates
            )
            result = session.execute(update_stmt)
            logger.info(f"Marked {result.rowcount} rules as not implemented for {WORKER_IDENTIFIER}.")

            session.commit()
            logger.info("Rule registry DB update complete.")

    except Exception as e:
        logger.error(f"Failed to update rule registry in DB: {e}", exc_info=True)

# --- Worker Initialization ---
logger.info("Dataset worker starting up...")

# 1. Discover rules - populates the global WORKER_RULE_REGISTRY
discover_rules(module_path="services.cleaning_rules.implementations")

# 2. Update DB using the registry populated in *this* process
#    We copy it here just to pass it cleanly to the function.
initial_registry_view = WORKER_RULE_REGISTRY.copy()
update_rule_registry_in_db(initial_registry_view)

# 3. Create Celery app instance
#    The tasks themselves will now access the registry snapshot when needed.
celery_app = create_celery_app(
    main_name="dataset_worker",
    include_tasks=["app.tasks"]
)
logger.info("Celery app created for dataset worker.")
