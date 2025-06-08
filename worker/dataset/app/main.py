# worker/dataset/app/main.py

import logging
from typing import Any, Dict, List

# Corrected import path for discover_rules and registry
from services.cleaning_rules.base import (
    WORKER_RULE_REGISTRY,
    RuleDefinition,
    discover_rules,
)

from services.factories.feature_selection_factory import FeatureSelectionStrategyFactory
from shared.db.models.feature_selection_definition import FeatureSelectionDefinitionDB

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.celery_config.app import create_celery_app
from shared.core.config import settings
from shared.db.models import CleaningRuleDefinitionDB
from shared.db_session import get_sync_db_session

# Use standard logging
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)

WORKER_IDENTIFIER = "dataset-worker"

def sync_definitions_to_db():
    """Upserts feature selection algorithm definitions into the database on worker startup."""
    logger.info("Syncing feature selection definitions to database...")
    factory = FeatureSelectionStrategyFactory()
    definitions = factory.get_all_definitions()
    worker_id = "dataset-worker"

    if not definitions:
        logger.info("No feature selection definitions found in factory to sync.")
        return

    try:
        with get_sync_db_session() as session:
            # Mark old definitions from this worker as not implemented
            # This handles cases where an algorithm is removed from the worker code
            type_names = {d.name for d in definitions}  # Use attribute access instead of dict subscription
            session.query(FeatureSelectionDefinitionDB)\
                   .filter(FeatureSelectionDefinitionDB.last_updated_by == worker_id,
                           ~FeatureSelectionDefinitionDB.name.in_(type_names))\
                   .update({'is_implemented': False})

            # Convert Pydantic models to dictionaries and prepare data for upsert
            definitions_to_upsert = []
            for definition in definitions:
                db_data = definition.model_dump(mode="json")  # Convert to dict
                db_data['last_updated_by'] = worker_id
                definitions_to_upsert.append(db_data)

            if definitions_to_upsert:
                upsert_stmt = pg_insert(FeatureSelectionDefinitionDB).values(definitions_to_upsert)
                update_on_conflict = upsert_stmt.on_conflict_do_update(
                    index_elements=['name'],
                    set_={
                        'display_name': upsert_stmt.excluded.display_name,
                        'description': upsert_stmt.excluded.description,
                        'parameters': upsert_stmt.excluded.parameters,
                        'is_implemented': upsert_stmt.excluded.is_implemented,
                        'last_updated_by': upsert_stmt.excluded.last_updated_by
                    }
                )
                session.execute(update_on_conflict)
            
            session.commit()
            logger.info(f"Successfully synced {len(definitions)} feature selection definitions to DB.")
    except Exception as e:
        logger.error(f"Failed to sync feature selection definitions to DB: {e}", exc_info=True)

def update_rule_registry_in_db(registry_snapshot: Dict[str, Any]):
    """UPSERTs rule definitions into the database using a snapshot of the registry."""
    logger.info("Updating cleaning rule registry in database...")
    discovered_rule_names = set(registry_snapshot.keys())
    definitions_to_upsert: List[Dict[str, Any]] = []

    for rule_name, rule_cls in registry_snapshot.items():
        try:
            instance = rule_cls()
            definition: RuleDefinition = instance.get_definition()
            db_data = definition.model_dump(mode="json")  # Use model_dump
            db_data["is_implemented"] = True
            db_data["last_updated_by"] = WORKER_IDENTIFIER
            definitions_to_upsert.append(db_data)
        except Exception as e:
            logger.error(
                f"Failed to get definition for rule '{rule_name}': {e}", exc_info=True
            )

    if not definitions_to_upsert and not discovered_rule_names:
        logger.warning(
            "No rule definitions discovered or to upsert. DB registry not updated."
        )
        return

    try:
        with get_sync_db_session() as session:
            # --- UPSERT Logic ---
            if definitions_to_upsert:
                logger.info(
                    f"Upserting {len(definitions_to_upsert)} rule definitions into DB..."
                )
                # Ensure 'name' is the index element
                insert_stmt = pg_insert(CleaningRuleDefinitionDB).values(
                    definitions_to_upsert
                )
                # Define update columns based on the model, excluding the primary key 'name'
                update_columns = {
                    col.name: getattr(insert_stmt.excluded, col.name)
                    for col in CleaningRuleDefinitionDB.__table__.columns
                    if col.name != "name"
                }
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["name"],  # Correct index element name
                    set_=update_columns,
                )
                session.execute(upsert_stmt)

            # --- Mark missing rules as not implemented ---
            # Only mark as unimplemened if they were previously known by *this* worker
            # AND are not in the currently discovered set.
            logger.info(
                f"Marking rules not implemented by {WORKER_IDENTIFIER} if previously known and not currently discovered..."
            )
            update_stmt = (
                update(CleaningRuleDefinitionDB)
                .where(
                    CleaningRuleDefinitionDB.last_updated_by == WORKER_IDENTIFIER,
                    ~CleaningRuleDefinitionDB.name.in_(
                        discovered_rule_names
                    ),  # Use discovered_rule_names set
                )
                .values(is_implemented=False, last_updated_by=WORKER_IDENTIFIER)
                .execution_options(synchronize_session=False)
            )
            result = session.execute(update_stmt)
            logger.info(
                f"Marked {result.rowcount} rules as not implemented for {WORKER_IDENTIFIER}."
            )

            session.commit()
            logger.info("Rule registry DB update complete.")

    except Exception as e:
        logger.error(f"Failed to update rule registry in DB: {e}", exc_info=True)
        # Consider if this should prevent worker startup


# --- Worker Initialization ---
logger.info("Dataset worker starting up...")
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(
    f"Result Backend: {'Configured' if settings.CELERY_RESULT_BACKEND else 'Not Configured'}"
)


#  Discover rules - populates the global WORKER_RULE_REGISTRY
#    Ensure the path is correct relative to the execution directory or adjust PYTHONPATH
discover_rules(module_path="services.cleaning_rules.implementations")

#  Update DB using the registry populated in *this* process
#    We copy it here just to pass it cleanly to the function.
initial_registry_view = WORKER_RULE_REGISTRY.copy()
update_rule_registry_in_db(initial_registry_view)

#  Sync feature selection definitions to DB
sync_definitions_to_db()

#  Create Celery app instance
#    The tasks themselves will now access the registry snapshot when needed via DependencyProvider.
celery_app = create_celery_app(
    main_name="dataset_worker",
    include_tasks=["app.tasks"],  # Path relative to where celery worker cmd is run
)
logger.info("Celery app created for dataset worker.")
