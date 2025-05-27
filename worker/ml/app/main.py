# worker/ml/app/main.py
import logging
from typing import Any, Dict, List

from shared.celery_config.app import create_celery_app
from shared.core.config import settings
from shared.db_session.sync_session import get_sync_db_session
from shared.repositories.ml_model_type_definition_repository import MLModelTypeDefinitionRepository
from shared.schemas.enums import ModelTypeEnum
from shared.schemas.ml_model_type_definition import HyperparameterDefinitionSchema
from services.strategies.lightgbm_strategy import LightGBMStrategy
from services.strategies.sklearn_strategy import SklearnStrategy
from services.strategies.xgboost_strategy import XGBoostStrategy 

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

logger.info("ML worker starting up...")

# Create the Celery app instance for the ML worker
celery_app = create_celery_app(
    main_name="ml_worker",
    include_tasks=["app.tasks"],  # Path relative to where celery worker cmd is run
)

# Optional: Add ML worker-specific Celery config here if needed
# celery_app.conf.update(
#     # Example: Set prefetch multiplier if needed for GPU tasks
#     worker_prefetch_multiplier=1,
# )

WORKER_IDENTIFIER = "ml-worker" # Identifier for this worker

def discover_and_prepare_model_type_definitions() -> List[Dict[str, Any]]:
    """
    Discovers model types and their hyperparameter schemas from strategies.
    Returns a list of dictionaries suitable for DB upsertion.
    """
    definitions_for_db: List[Dict[str, Any]] = []
    
    # List all strategy classes that define supported model types
    strategy_classes = [
        SklearnStrategy,
        XGBoostStrategy,
        LightGBMStrategy,
        # Add other strategy classes here
    ]

    discovered_type_names = set()

    for strategy_cls in strategy_classes:
        if hasattr(strategy_cls, 'get_supported_model_types_with_schemas'):
            try:
                # Call the static method
                supported_types_map: Dict[ModelTypeEnum, List[HyperparameterDefinitionSchema]] = \
                    strategy_cls.get_supported_model_types_with_schemas()
                
                for model_type_enum, schema_list in supported_types_map.items():
                    type_name_str = model_type_enum.value # Get the string value of the enum
                    if type_name_str in discovered_type_names:
                        logger.warning(f"Model type '{type_name_str}' schema already defined by another strategy. Skipping re-definition from {strategy_cls.__name__}.")
                        continue
                    
                    discovered_type_names.add(type_name_str)

                    # Create a display name (can be improved)
                    display_name = type_name_str.replace("sklearn_", "Scikit-Learn ").replace("_", " ").title()
                    if "Xgboost" in display_name: display_name = display_name.replace("Xgboost", "XGBoost")
                    if "Lightgbm" in display_name: display_name = display_name.replace("Lightgbm", "LightGBM")
                    
                    # Convert HyperparameterDefinitionSchema to dicts
                    schema_as_dicts = [s.model_dump(mode="json") for s in schema_list]

                    definitions_for_db.append({
                        "type_name": type_name_str,
                        "display_name": display_name,
                        "description": f"{display_name} model type.", # Basic description
                        "hyperparameter_schema": schema_as_dicts,
                        "is_enabled": True, # Default to enabled
                        "last_updated_by": WORKER_IDENTIFIER,
                    })
                    logger.debug(f"Discovered model type: {type_name_str} with {len(schema_list)} HP definitions from {strategy_cls.__name__}")
            except Exception as e:
                logger.error(f"Error discovering model types from strategy {strategy_cls.__name__}: {e}", exc_info=True)
        else:
            logger.warning(f"Strategy {strategy_cls.__name__} does not have 'get_supported_model_types_with_schemas' method.")
            
    return definitions_for_db

def update_model_type_registry_in_db():
    """
    Discovers model type definitions and upserts them into the database.
    """
    logger.info("Updating ML model type registry in database...")
    definitions = discover_and_prepare_model_type_definitions()

    if not definitions:
        logger.warning("No ML model type definitions discovered. DB registry not updated.")
        # Still call upsert with empty list to allow cleanup of old entries by this worker
    
    try:
        # Use get_sync_db_session for a synchronous session suitable for startup
        with get_sync_db_session() as session:
            repo = MLModelTypeDefinitionRepository(lambda: session) # Pass lambda for session factory
            repo.upsert_model_type_definitions(definitions, WORKER_IDENTIFIER)
        logger.info("ML model type registry DB update complete.")
    except Exception as e:
        logger.error(f"Failed to update ML model type registry in DB: {e}", exc_info=True)


logger.info("Celery app created for ML worker.")

#Discover and update ML model type definitions in DB
update_model_type_registry_in_db()

# Initialize Optuna storage (can be done here or lazy-loaded in tasks)
# This ensures Optuna knows about the DB URL early.
try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.DEBUG)
    # Check if the database URL is set
    if settings.OPTUNA_DB_URL:
        # This doesn't create tables, just configures Optuna's default storage factory
        optuna.storages.RDBStorage(url=str(settings.OPTUNA_DB_URL))
        logger.info("Optuna RDBStorage configured with URL from settings.")
        # Actual study creation will handle table creation if needed.
    else:
        logger.warning("OPTUNA_DB_URL not set. Optuna will use in-memory storage.")
except ImportError:
    logger.warning(
        "Optuna library not found. Hyperparameter search features will be unavailable."
    )
except Exception as e:
    logger.error(f"Error configuring Optuna storage: {e}", exc_info=True)
