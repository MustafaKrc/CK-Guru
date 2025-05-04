# shared/repositories/ck_metric_repository.py
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .base_repository import BaseRepository
from shared.db.models import CKMetric

logger = logging.getLogger(__name__)

class CKMetricRepository(BaseRepository[CKMetric]):
    """Handles database operations for CKMetric."""

    def get_metrics_for_commit(self, repo_id: int, commit_hash: str) -> List[CKMetric]:
        """Retrieves all CK metrics for a specific commit."""
        with self._session_scope() as session:
            stmt = select(CKMetric).where(
                CKMetric.repository_id == repo_id,
                CKMetric.commit_hash == commit_hash
            ).order_by(CKMetric.file, CKMetric.class_name)
            return session.execute(stmt).scalars().all()

    def bulk_upsert(self, ck_metrics: List[Dict[str, Any]]) -> int:
        """
        Performs a bulk UPSERT of CKMetric data.

        Args:
            ck_metrics: A list of dictionaries, each representing a CK metric record.
                        Keys must match CKMetric model attribute names (e.g., 'class_name').

        Returns:
            The number of rows processed (inserted or updated).
        """
        if not ck_metrics:
            return 0

        processed_count = 0
        with self._session_scope() as session:
            try:
                model_cols = {c.name for c in CKMetric.__table__.columns}
                for row in ck_metrics:
                    for col in model_cols:
                        row.setdefault(col, None)        # or null() for explicit SQL NULL

                constraint_name = 'uq_ck_metric_key'
                stmt = pg_insert(CKMetric).on_conflict_do_update(
                    constraint=constraint_name,
                    set_={c.name: getattr(pg_insert(CKMetric).excluded, c.name)
                        for c in CKMetric.__table__.c
                        if c.name not in ('id','repository_id','commit_hash','file','class_name')}
                )

                with self._session_scope() as session:
                    session.execute(stmt, ck_metrics)    # executemany
                    session.commit()

                # rowcount might not be reliable across backends for UPSERT
                # For simplicity, return the number of input records as processed count
                processed_count = len(ck_metrics)
                logger.info(f"CKMetricRepository: Bulk UPSERT processed {processed_count} records.")

            except SQLAlchemyError as e:
                logger.error(f"CKMetricRepository: Database error during bulk UPSERT: {e}", exc_info=True)
                raise # Re-raise to be handled by caller
            except Exception as e:
                logger.error(f"CKMetricRepository: Unexpected error during bulk UPSERT: {e}", exc_info=True)
                raise

        return processed_count

    def get_metrics_dataframe_for_commit(self, repo_id: int, commit_hash: str) -> pd.DataFrame:
        """Retrieves CK metrics for a commit and returns them as a Pandas DataFrame."""
        metrics = self.get_metrics_for_commit(repo_id, commit_hash)
        if not metrics:
            return pd.DataFrame()

        # Convert list of ORM objects to DataFrame
        # Make sure column names match the expected DataFrame structure (e.g., alias 'class_name' back to 'class')
        data = [
            {
                'file': m.file,
                'class': m.class_name, # Alias back if needed by CK runner logic comparison
                'type': m.type_,      # Alias back if needed
                'cbo': m.cbo, 'cboModified': m.cboModified, 'fanin': m.fanin, 'fanout': m.fanout,
                'wmc': m.wmc, 'dit': m.dit, 'noc': m.noc, 'rfc': m.rfc, 'lcom': m.lcom,
                'lcom_norm': m.lcom_norm,
                'tcc': m.tcc, 'lcc': m.lcc, 'totalMethodsQty': m.totalMethodsQty,
                'staticMethodsQty': m.staticMethodsQty, 'publicMethodsQty': m.publicMethodsQty,
                'privateMethodsQty': m.privateMethodsQty, 'protectedMethodsQty': m.protectedMethodsQty,
                'defaultMethodsQty': m.defaultMethodsQty, 'visibleMethodsQty': m.visibleMethodsQty,
                'abstractMethodsQty': m.abstractMethodsQty, 'finalMethodsQty': m.finalMethodsQty,
                'synchronizedMethodsQty': m.synchronizedMethodsQty, 'totalFieldsQty': m.totalFieldsQty,
                'staticFieldsQty': m.staticFieldsQty, 'publicFieldsQty': m.publicFieldsQty,
                'privateFieldsQty': m.privateFieldsQty, 'protectedFieldsQty': m.protectedFieldsQty,
                'defaultFieldsQty': m.defaultFieldsQty, 'finalFieldsQty': m.finalFieldsQty,
                'synchronizedFieldsQty': m.synchronizedFieldsQty, 'nosi': m.nosi, 'loc': m.loc,
                'returnQty': m.returnQty, 'loopQty': m.loopQty, 'comparisonsQty': m.comparisonsQty,
                'tryCatchQty': m.tryCatchQty, 'parenthesizedExpsQty': m.parenthesizedExpsQty,
                'stringLiteralsQty': m.stringLiteralsQty, 'numbersQty': m.numbersQty,
                'assignmentsQty': m.assignmentsQty, 'mathOperationsQty': m.mathOperationsQty,
                'variablesQty': m.variablesQty, 'maxNestedBlocksQty': m.maxNestedBlocksQty,
                'anonymousClassesQty': m.anonymousClassesQty, 'innerClassesQty': m.innerClassesQty,
                'lambdasQty': m.lambdasQty, 'uniqueWordsQty': m.uniqueWordsQty,
                'modifiers': m.modifiers, 'logStatementsQty': m.logStatementsQty
            }
            for m in metrics
        ]
        df = pd.DataFrame(data)
        logger.debug(f"CKMetricRepository: Retrieved {len(df)} CK metrics as DataFrame for commit {commit_hash[:7]}.")
        return df
    
    def check_metrics_exist_for_commit(self, repo_id: int, commit_hash: str) -> bool:
        """Checks if any CK metrics exist in the DB for a specific commit."""
        with self._session_scope() as session:
            stmt = select(CKMetric.id).where(
                CKMetric.repository_id == repo_id,
                CKMetric.commit_hash == commit_hash
            ).limit(1) # Optimization: only need to find one record
            # Alternative using exists():
            # stmt_exists = select(exists().where(
            #     CKMetric.repository_id == repo_id,
            #     CKMetric.commit_hash == commit_hash
            # ))
            # result = session.execute(stmt_exists).scalar()
            result = session.execute(stmt).first()
            exists_flag = result is not None
            logger.debug(f"CKMetricRepository: Check existence for commit {commit_hash[:7]} -> {exists_flag}")
            return exists_flag