# worker/ml/app/tasks.py
import logging
from typing import Dict, Optional
from celery import shared_task, Task
import lime
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

# Import Handlers (adjust path if needed)
from services.handlers.training_handler import TrainingJobHandler
from services.handlers.hp_search_handler import HPSearchJobHandler
from services.handlers.inference_handler import InferenceJobHandler
# Import job DB service if needed for direct updates (though handlers should manage)
# from services import job_db_service

# Import shared components
from shared.db.models.dataset import Dataset
from shared.db.models.inference_job import InferenceJob
from shared.db.models.ml_model import MLModel
from shared.db.models.xai_result import XAIResult
from shared.schemas.enums import DatasetStatusEnum, XAITypeEnum, XAIStatusEnum, ModelTypeEnum # Import enums
from shared.db_session import get_sync_db_session
from services import feature_db_service
from services.artifact_service import artifact_service
from shared.schemas.xai import CounterfactualExample, CounterfactualResultData, DecisionPathEdge, DecisionPathNode, DecisionPathResultData, FeatureImportanceResultData, FeatureImportanceValue, FeatureSHAPValue, InstanceCounterfactualResult, InstanceDecisionPath, InstanceLIMEResult, InstanceSHAPResult, LIMEResultData, SHAPResultData
from .main import celery_app # Import app instance for sending tasks

import dice_ml
from dice_ml.utils import helpers

from celery.exceptions import Ignore, Terminated, Reject
from services.xai_db_service import create_pending_xai_result_sync, update_xai_result_sync

from shared.core.config import settings

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

@shared_task(bind=True, name='tasks.train_model')
def train_model_task(self: Task, training_job_id: int):
    """Celery task facade for training jobs."""
    logger.info(f"Task {self.request.id}: Received training request for Job ID {training_job_id}")
    try:
        handler = TrainingJobHandler(training_job_id, self)
        # The handler's run_job method now manages the entire lifecycle,
        # including DB updates and Celery state updates.
        return handler.run_job()
    except Exception as e:
        # Log uncaught exceptions from handler instantiation or run_job setup
        # Note: run_job itself has robust error handling, this is a safety net
        logger.critical(f"Task {self.request.id}: Unhandled exception during training job {training_job_id} execution: {e}", exc_info=True)
        # Ensure task is marked as failed if exception escapes run_job's finally block
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        # Re-raise to ensure Celery knows it failed critically
        raise

@shared_task(bind=True, name='tasks.hyperparameter_search')
def hyperparameter_search_task(self: Task, hp_search_job_id: int):
    """Celery task facade for hyperparameter search jobs."""
    logger.info(f"Task {self.request.id}: Received HP search request for Job ID {hp_search_job_id}")
    try:
        handler = HPSearchJobHandler(hp_search_job_id, self)
        return handler.run_job()
    except Exception as e:
        logger.critical(f"Task {self.request.id}: Unhandled exception during HP search job {hp_search_job_id} execution: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        raise

@shared_task(bind=True, name='tasks.inference')
def inference_task(self: Task, inference_job_id: int):
    """
    Runs inference and then dispatches separate background tasks for XAI generation.
    """
    logger.info(f"Task {self.request.id}: Received inference execution request for InferenceJob ID {inference_job_id}")
    job_successful = False
    handler: Optional[InferenceJobHandler] = None # Initialize handler

    try:
        handler = InferenceJobHandler(inference_job_id, self)
        # run_job performs prediction, updates InferenceJob with prediction results
        prediction_results_dict = handler.run_job()
        job_successful = True # Mark prediction as successful

    except (Ignore, Terminated) as celery_exc:
        # Handler's run_job should re-raise these - let Celery handle state
        logger.info(f"Task {self.request.id}: Inference task ignored or terminated for job {inference_job_id}.")
        raise # Re-raise to Celery
    except Exception as e:
        logger.error(f"Task {self.request.id}: Inference handler run_job failed for job {inference_job_id}. No XAI tasks will be dispatched.", exc_info=True)
        # Ensure Celery state is FAILURE if handler didn't set it
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # Do not proceed to XAI dispatch
        return # Exit task

    # --- Dispatch XAI Tasks If Prediction Succeeded ---
    if job_successful and handler and handler.job_db_record and handler.model_strategy and handler.model_strategy.model:
        logger.info(f"Task {self.request.id}: Inference successful for job {inference_job_id}. Dispatching background XAI tasks...")

        xai_types_to_generate = [
            XAITypeEnum.SHAP,
            XAITypeEnum.FEATURE_IMPORTANCE,
            XAITypeEnum.LIME,
            XAITypeEnum.COUNTERFACTUALS
        ]
        model_obj = handler.model_strategy.model
        # Use isinstance for safer type checking
        if isinstance(model_obj, (getattr(__import__('sklearn.ensemble', fromlist=['RandomForestClassifier']), 'RandomForestClassifier', None),
                                  getattr(__import__('sklearn.tree', fromlist=['DecisionTreeClassifier']), 'DecisionTreeClassifier', None))):
             # Check for specific compatible types if possible
             if XAITypeEnum.DECISION_PATH not in xai_types_to_generate:
                 xai_types_to_generate.append(XAITypeEnum.DECISION_PATH)
        # Add other conditional checks (e.g., for COUNTERFACTUALS) later

        xai_task_name = 'tasks.generate_explanation'
        xai_queue = 'xai_queue' # Use dedicated queue

        with get_sync_db_session() as xai_session:
            dispatched_count = 0
            for xai_type in xai_types_to_generate:
                # 1. Create Pending XAIResult DB Entry
                xai_result_id = create_pending_xai_result_sync(xai_session, inference_job_id, xai_type)

                if xai_result_id is None:
                     logger.error(f"Failed to create DB record for XAI type {xai_type.value}. Skipping dispatch.")
                     continue

                # 2. Dispatch Celery Task
                try:
                    logger.info(f"Dispatching task '{xai_task_name}' for XAIResult ID {xai_result_id} (Type: {xai_type.value}) to queue '{xai_queue}'...")
                    celery_app.send_task(
                        xai_task_name,
                        args=[xai_result_id],
                        queue=xai_queue
                    )
                    dispatched_count += 1
                except Exception as dispatch_err:
                    logger.error(f"Failed to dispatch XAI task for XAIResult ID {xai_result_id}: {dispatch_err}", exc_info=True)
                    # Update the created record to FAILED immediately
                    update_xai_result_sync(xai_session, xai_result_id, XAIStatusEnum.FAILED,
                                           message=f"Failed to dispatch generation task: {dispatch_err}",
                                           commit=False) # Commit handled below

            # Commit all created/updated XAIResult records
            try:
                xai_session.commit()
                logger.info(f"Committed {dispatched_count} pending/failed XAIResult records to DB for Job {inference_job_id}.")
            except Exception as commit_err:
                 logger.error(f"Failed to commit pending XAIResult records: {commit_err}", exc_info=True)
                 xai_session.rollback()

    # Return the original prediction results dictionary (doesn't include XAI status)
    return prediction_results_dict


@shared_task(bind=True, name='tasks.generate_explanation', acks_late=True)
def generate_explanation_task(self: Task, xai_result_id: int):
    """
    Generates a specific XAI explanation based on the XAIResult record ID.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting explanation generation for XAIResult ID {xai_result_id}")
    status_message = "XAI generation failed."
    final_status = XAIStatusEnum.FAILED
    result_data_json: Optional[Dict] = None
    session: Optional[Session] = None # Define session outside try

    try:
        with get_sync_db_session() as session:
            # 1. Load Records and Update Status
            xai_record = session.get(XAIResult, xai_result_id)
            if not xai_record: 
                raise Ignore(f"XAIResult record {xai_result_id} not found. Ignoring task.")
            if xai_record.status == XAIStatusEnum.RUNNING and xai_record.celery_task_id != task_id:
                raise Ignore(f"XAIResult {xai_result_id} already running under task {xai_record.celery_task_id}.")
            if xai_record.status in [XAIStatusEnum.SUCCESS, XAIStatusEnum.FAILED]:
                raise Ignore(f"XAIResult {xai_result_id} already in terminal state {xai_record.status.value}.")

            inference_job = session.get(InferenceJob, xai_record.inference_job_id)
            if not inference_job: 
                raise ValueError(f"InferenceJob {xai_record.inference_job_id} not found.")
            ml_model_record = session.get(MLModel, inference_job.ml_model_id)
            if not ml_model_record: 
                raise ValueError(f"MLModel {inference_job.ml_model_id} not found.")
            if not ml_model_record.s3_artifact_path: 
                raise ValueError(f"MLModel {ml_model_record.id} has no artifact path.")

            # Update status to RUNNING - use sync service function
            update_xai_result_sync(session, xai_result_id, XAIStatusEnum.RUNNING,
                                   message="Explanation generation started.", task_id=task_id,
                                   is_start=True, commit=True) # Commit this update
            logger.info(f"XAIResult {xai_result_id} status set to RUNNING.")

            # 2. Extract necessary info
            xai_type = xai_record.xai_type
            repo_id = inference_job.input_reference.get('repo_id')
            commit_hash = inference_job.input_reference.get('commit_hash')
            artifact_path = ml_model_record.s3_artifact_path
            training_dataset_id = ml_model_record.dataset_id

            if not repo_id or not commit_hash: 
                raise ValueError("repo_id or commit_hash missing.")

            # 3. Load Model
            logger.info(f"Loading model artifact: {artifact_path}")
            model = artifact_service.load_artifact(artifact_path)
            if not model: 
                raise RuntimeError(f"Failed to load model artifact from {artifact_path}")

            # 4. Fetch Features
            logger.info(f"Fetching features for repo={repo_id}, commit={commit_hash[:7]}")
            features_df = feature_db_service.get_features_for_commit(session, repo_id, commit_hash)
            if features_df is None or features_df.empty: 
                raise ValueError(f"Could not retrieve features for commit {commit_hash[:7]}")

            # 5. Prepare Data (separate features/ids, get feature names)
            identifier_cols = ['file', 'class_name']
            identifiers_df = features_df[[col for col in identifier_cols if col in features_df.columns]].copy()
            feature_names = features_df.columns.difference(identifier_cols).tolist()
            # Ensure correct feature order
            if hasattr(model, 'feature_names_in_'):
                expected_features = model.feature_names_in_.tolist()
                missing = set(expected_features) - set(feature_names)
                if missing: raise ValueError(f"Feature mismatch: DB features missing {missing}")
                feature_names = expected_features # Use model's order
            X_inference = features_df[feature_names].fillna(0).copy() # Ensure fillna matches training

            # 6. Fetch Background Data (Conditional)
            background_data_df: Optional[pd.DataFrame] = None
            if xai_type in [XAITypeEnum.LIME]: # Add others if needed
                logger.info(f"XAI type {xai_type.value} requires background data. Attempting load...")
                if training_dataset_id:
                    dataset_record = session.get(Dataset, training_dataset_id)
                    if dataset_record and dataset_record.status == DatasetStatusEnum.READY and dataset_record.storage_path:
                        try:
                            background_data_df = pd.read_parquet(dataset_record.storage_path, columns=feature_names, storage_options=settings.s3_storage_options)
                            # Simple sampling for now
                            if len(background_data_df) > 500: background_data_df = background_data_df.sample(n=500, random_state=42)
                            logger.info(f"Loaded background data ({background_data_df.shape}) from training dataset {training_dataset_id}.")
                        except Exception as load_err: logger.error(f"Failed to load background dataset {training_dataset_id}: {load_err}", exc_info=True)
                    else: logger.warning(f"Training dataset {training_dataset_id} not ready/found.")
                else: logger.warning("MLModel record has no dataset_id for background data.")
                if background_data_df is None or background_data_df.empty:
                     logger.warning("Using inference data sample as background data (less accurate).")
                     background_data_df = shap.sample(X_inference, min(50, X_inference.shape[0]))

            # 7. Calculate Explanation
            logger.info(f"Calculating explanation type: {xai_type.value}...")
            result_data_obj = None # Initialize
            if xai_type == XAITypeEnum.SHAP:
                explainer = shap.TreeExplainer(model) # TODO: Make explainer dynamic
                shap_values_pos_class = explainer.shap_values(X_inference)[1]
                instance_results = []
                for i in range(len(identifiers_df)):
                    instance_list = [FeatureSHAPValue(feature=fn, value=round(float(sv), 4)) for fn, sv in zip(feature_names, shap_values_pos_class[i])]
                    instance_results.append(InstanceSHAPResult(file=identifiers_df.iloc[i].get('file'), class_name=identifiers_df.iloc[i].get('class_name'), shap_values=instance_list))
                result_data_obj = SHAPResultData(instance_shap_values=instance_results)
                final_status = XAIStatusEnum.SUCCESS
                status_message = "SHAP explanation generated successfully."

            elif xai_type == XAITypeEnum.FEATURE_IMPORTANCE:
                explainer = shap.TreeExplainer(model)
                shap_values_pos_class = explainer.shap_values(X_inference)[1]
                avg_abs_shap = np.mean(np.abs(shap_values_pos_class), axis=0)
                importance_list = [FeatureImportanceValue(feature=fn, importance=round(float(imp), 4)) for fn, imp in zip(feature_names, avg_abs_shap)]
                importance_list.sort(key=lambda x: x.importance, reverse=True)
                result_data_obj = FeatureImportanceResultData(feature_importances=importance_list)
                final_status = XAIStatusEnum.SUCCESS
                status_message = "Feature importance derived from SHAP successfully."

            elif xai_type == XAITypeEnum.LIME:
                if background_data_df is None or background_data_df.empty: raise ValueError("Background data required for LIME is missing.")
                explainer = lime.lime_tabular.LimeTabularExplainer(background_data_df.values, feature_names=feature_names, class_names=['clean', 'defect-prone'], mode='classification', random_state=42)
                instance_results = []
                num_features_lime = min(10, len(feature_names)) # Limit LIME features
                for i in range(len(X_inference)):
                    explanation = explainer.explain_instance(X_inference.iloc[i].values, model.predict_proba, num_features=num_features_lime)
                    lime_explanation = [(feature, round(float(weight), 4)) for feature, weight in explanation.as_list()]
                    instance_results.append(InstanceLIMEResult(file=identifiers_df.iloc[i].get('file'), class_name=identifiers_df.iloc[i].get('class_name'), explanation=lime_explanation))
                result_data_obj = LIMEResultData(instance_lime_values=instance_results)
                final_status = XAIStatusEnum.SUCCESS
                status_message = "LIME explanation generated successfully."

            elif xai_type == XAITypeEnum.DECISION_PATH:
                try:
                    if isinstance(model, (RandomForestClassifier, DecisionTreeClassifier)):
                        instance_paths = []
                        num_trees_to_explain = 3 # Limit explanation to N trees for RandomForest
                        estimators = model.estimators_ if isinstance(model, RandomForestClassifier) else [model]

                        for i in range(len(X_inference)):
                            instance_feature_vector = X_inference.iloc[[i]]
                            tree_count = 0
                            for estimator in estimators:
                                if tree_count >= num_trees_to_explain and isinstance(model, RandomForestClassifier): break
                                tree_ = estimator.tree_
                                if not tree_: continue # Skip if tree structure isn't available

                                feature = tree_.feature
                                threshold = tree_.threshold
                                node_indicator = estimator.decision_path(instance_feature_vector)
                                node_index = node_indicator.indices

                                path_nodes_struct = []
                                path_edges_struct = []
                                for node_id_idx in range(len(node_index)):
                                    node_id = node_index[node_id_idx]
                                    is_leaf = tree_.children_left[node_id] == tree_.children_right[node_id]
                                    condition = None
                                    if not is_leaf:
                                        feat_idx = feature[node_id]
                                        thresh_val = round(threshold[node_id], 3)
                                        feature_name = feature_names[feat_idx] if feat_idx >= 0 and feat_idx < len(feature_names) else f"feature_{feat_idx}"
                                        condition = f"{feature_name} <= {thresh_val}"

                                    node_info = DecisionPathNode(
                                         id=str(node_id),
                                         condition=condition if not is_leaf else "Leaf",
                                         samples=int(tree_.n_node_samples[node_id]),
                                         value=[int(v) for v in tree_.value[node_id][0]]
                                    )
                                    path_nodes_struct.append(node_info)

                                    # Add edge from previous node if not the first node
                                    if node_id_idx > 0:
                                        prev_node_id = node_index[node_id_idx - 1]
                                        # Determine label (True if went left, False if right)
                                        label = "True" if node_id == tree_.children_left[prev_node_id] else "False"
                                        path_edges_struct.append(DecisionPathEdge(source=str(prev_node_id), target=str(node_id), label=label))

                                instance_paths.append(InstanceDecisionPath(
                                    file=identifiers_df.iloc[i].get('file'),
                                    class_name=identifiers_df.iloc[i].get('class_name'),
                                    tree_index=getattr(estimator, 'random_state', 0) if isinstance(model, RandomForestClassifier) else None, # Use random_state as tree index proxy
                                    nodes=path_nodes_struct,
                                    edges=path_edges_struct,
                                    path_node_ids=[str(n) for n in node_index]
                                ))
                                tree_count += 1

                        if instance_paths:
                            result_data_obj = DecisionPathResultData(instance_decision_paths=instance_paths)
                            final_status = XAIStatusEnum.SUCCESS
                            status_message = f"Decision Path examples generated."
                        else:
                             status_message = "No decision paths could be extracted."
                             final_status = XAIStatusEnum.FAILED
                    else:
                        status_message = f"Decision Path not supported for model type: {type(model)}"
                        final_status = XAIStatusEnum.FAILED
                except Exception as path_err:
                    status_message = f"Decision Path calculation failed: {path_err}"
                    logger.error(status_message, exc_info=True)
                    final_status = XAIStatusEnum.FAILED
                    
            elif xai_type == XAITypeEnum.COUNTERFACTUALS:
                try:
                    if not hasattr(model, 'predict_proba'): # Keep predict_proba check
                        raise TypeError("Model needs predict_proba for DiCE integration.")
                    # Even without background data, we need features AND the model's prediction for the inference instances
                    # We need the prediction made by the model for the instances we are explaining
                    logger.info("Getting model predictions for DiCE Data object...")
                    y_pred_inference = model.predict(X_inference) # Get predictions (0 or 1)

                    # --- Create DataFrame with Features AND Predicted Outcome ---
                    data_for_dice = X_inference.copy()
                    # Add the prediction as the outcome column DiCE expects
                    # Make sure the outcome name matches what DiCE will use
                    outcome_col_name = 'predicted_outcome' # Use a distinct name
                    data_for_dice[outcome_col_name] = y_pred_inference

                    # If using background data, ensure it ALSO has the outcome column defined
                    if background_data_df is not None and not background_data_df.empty:
                        # We need the TRUE outcome from the training set for background data
                        # This assumes the loaded background_data_df includes the target variable
                        # (This adds complexity - need to load target col too if not already loaded)
                        # For now, let's assume background data loading handled this correctly OR
                        # DiCE can work with just the features for background. Revisit if needed.
                        logger.warning("Using background data for DiCE. Ensure it contains the correct outcome column if required by DiCE method.")
                        # If DiCE strictly needs outcome in background:
                        # if outcome_col not in background_data_df.columns: raise ValueError("Background data missing outcome column for DiCE.")

                        dice_data = dice_ml.Data(dataframe=background_data_df, # Use background if available
                                                continuous_features=feature_names,
                                                outcome_name=outcome_col_name) # Tell DiCE the name
                    else:
                        # Create Data object from inference data + predictions if no background data
                        logger.warning("Creating DiCE Data object from inference data + predictions. CF quality may vary.")
                        dice_data = dice_ml.Data(dataframe=data_for_dice, # Use combined df
                                                continuous_features=feature_names,
                                                outcome_name=outcome_col_name) # Tell DiCE the name


                    # Wrap the model
                    # DiCE needs a predict_proba like function, ensure model provides it
                    dice_model = dice_ml.Model(model=model, backend="sklearn") # Assumes sklearn

                    # Initialize DiCE explainer
                    dice_exp = dice_ml.Dice(dice_data, dice_model, method="random") # Random is often robust

                    cf_instance_results = []
                    # Only generate for instances predicted as defect-prone (1)
                    indices_to_explain = X_inference.index[y_pred_inference == 1] # Use the predictions we got

                    if len(indices_to_explain) == 0:
                        status_message = "No defect-prone instances found, skipping counterfactual generation."
                        final_status = XAIStatusEnum.SUCCESS
                    else:
                        logger.info(f"Generating counterfactuals for {len(indices_to_explain)} defect-prone instances...")
                        num_cfs_per_instance = 3

                        for i in indices_to_explain:
                            # Query instance MUST NOT contain the outcome column when passed to generate_counterfactuals
                            query_instance_features = X_inference.loc[[i]]
                            try:
                                counterfactuals = dice_exp.generate_counterfactuals(
                                    query_instance_features, # Pass only features
                                    total_CFs=num_cfs_per_instance,
                                    desired_class=0 # Target class 0 (clean)
                                )
                                cf_examples_structured = []
                                if counterfactuals and counterfactuals.cf_examples_list:
                                    for cf_example in counterfactuals.cf_examples_list:
                                        cf_df = cf_example.final_cfs_df # This DataFrame includes the predicted outcome by DiCE
                                        # Extract features and predicted outcome/probability from DiCE's output DF
                                        cf_features = cf_df.iloc[0][feature_names].to_dict()
                                        cf_pred_label = int(cf_df.iloc[0][outcome_col_name]) # Get DiCE's predicted outcome for the CF
                                        # Get probability from the original model if needed (DiCE might not provide it easily)
                                        cf_pred_proba = model.predict_proba(pd.DataFrame([cf_features]))[0]
                                        cf_prob_desired_class = float(cf_pred_proba[0]) # Probability of class 0

                                        cf_examples_structured.append(CounterfactualExample(
                                            features=cf_features,
                                            outcome_probability=round(cf_prob_desired_class, 4),
                                            outcome_label=cf_pred_label
                                        ))
                                cf_instance_results.append(InstanceCounterfactualResult(
                                    file=identifiers_df.loc[i].get('file'),
                                    class_name=identifiers_df.loc[i].get('class_name'),
                                    counterfactuals=cf_examples_structured
                                ))
                            except Exception as cf_inst_err:
                                logger.warning(f"Counterfactual generation failed for instance index {i}: {cf_inst_err}", exc_info=True)

                        if cf_instance_results:
                            result_data_obj = CounterfactualResultData(instance_counterfactuals=cf_instance_results)
                            final_status = XAIStatusEnum.SUCCESS
                            status_message = "Counterfactual explanation generation finished."
                        else:
                            status_message = "Counterfactual generation ran but found no examples."
                            final_status = XAIStatusEnum.SUCCESS

                except Exception as cf_err:
                    status_message = f"Counterfactual calculation failed: {cf_err}"
                    logger.error(status_message, exc_info=True)
                    final_status = XAIStatusEnum.FAILED

            else:
                status_message = f"Unsupported XAI type '{xai_type.value}' requested."
                final_status = XAIStatusEnum.FAILED

            # Convert result object to JSON dict if successful
            if result_data_obj and final_status == XAIStatusEnum.SUCCESS:
                result_data_json = result_data_obj.model_dump(exclude_none=True, mode='json')

            # 8. Update Final Status in DB (committed by context manager)
            # Use the sync update function, setting commit=False as context manager handles it
            update_xai_result_sync(session, xai_result_id, final_status, status_message, result_data_json, commit=False)

    except (Ignore, Terminated) as celery_exc:
        logger.info(f"Task {task_id} received Ignore/Terminated signal for XAIResult {xai_result_id}.")
        # Don't update DB here, Celery handles task state
        raise # Re-raise for Celery
    except Exception as e:
        session.rollback() # Rollback any potential changes if error occurred mid-processing
        status_message = f"Failed generation for XAIResult {xai_result_id}: {type(e).__name__}: {e}"
        logger.error(status_message, exc_info=True)
        final_status = XAIStatusEnum.FAILED
        # Update DB status to FAILED using the sync helper
        # Use a separate commit=True here as the main context might have rolled back
        update_xai_result_sync(session, xai_result_id, final_status, status_message, commit=True)
        raise Reject(status_message, requeue=False) from e

    # No explicit return value needed, task success/failure is based on exceptions/return