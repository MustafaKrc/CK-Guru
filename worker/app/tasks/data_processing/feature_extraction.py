# worker/app/tasks/feature_extraction.py (New file or integrate into repository_tasks.py)

import os
import subprocess
import shutil
from pathlib import Path
import pandas as pd
from git import Repo, GitCommandError
import logging
from typing import Set

# Use Celery's logger or standard logger configured in the task
logger = logging.getLogger(__name__) # Or get_task_logger(__name__)

# Define path to CK Jar inside the container (matches Dockerfile COPY destination)
CK_JAR_PATH = Path('/app/third_party/ck.jar')

def run_ck_tool(repo_dir: Path, output_dir: Path, commit_hash: str) -> pd.DataFrame:
    """
    Runs the CK tool on the specified repository directory for a specific commit.
    Cleans up intermediate CK output files.

    Args:
        repo_dir: Path to the checked-out repository.
        output_dir: Base directory where CK results for this repo are stored.
        commit_hash: The commit being analyzed (used for temporary output).

    Returns:
        DataFrame containing the CK class metrics, or empty DataFrame on error.
    """
    use_jars = "false"
    max_files_per_partition = 0
    variables_and_fields = "false"

    # Use a temporary, commit-specific folder for raw CK output to avoid conflicts
    ck_temp_output_dir = output_dir / f"temp_ck_{commit_hash}"

    if not CK_JAR_PATH.exists():
        logger.error(f"CK JAR not found at {CK_JAR_PATH}")
        raise FileNotFoundError(f"CK JAR not found at {CK_JAR_PATH}")

    if ck_temp_output_dir.exists():
        logger.warning(f"Removing existing temporary CK output dir: {ck_temp_output_dir}")
        shutil.rmtree(ck_temp_output_dir)
    ck_temp_output_dir.mkdir(parents=True, exist_ok=True)

    # --- Run CK ---
    try:
        logger.info(f"Running CK for commit {commit_hash} on {repo_dir}...")
        command = [
            'java', '-jar', str(CK_JAR_PATH), str(repo_dir),
            use_jars, str(max_files_per_partition), variables_and_fields,
            str(ck_temp_output_dir) # Pass temp dir to CK
        ]
        logger.debug(f"Executing command: {' '.join(command)}")

        # Increased timeout might be needed for large repos
        completed_process = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600 # Add a timeout (e.g., 10 minutes)
        )
        logger.debug(f"CK stdout for {commit_hash}:\n{completed_process.stdout.decode()}")
        if completed_process.stderr:
             logger.warning(f"CK stderr for {commit_hash}:\n{completed_process.stderr.decode()}")


    except subprocess.CalledProcessError as e:
        error_msg = f"Error running CK for commit {commit_hash}: {e.stderr.decode()}"
        logger.error(error_msg)
        # Clean up temp dir even on error
        if ck_temp_output_dir.exists():
            shutil.rmtree(ck_temp_output_dir)
        return pd.DataFrame() # Return empty DF on error
    except subprocess.TimeoutExpired:
        error_msg = f"CK timed out for commit {commit_hash} after 600 seconds."
        logger.error(error_msg)
        if ck_temp_output_dir.exists():
            shutil.rmtree(ck_temp_output_dir)
        return pd.DataFrame() # Return empty DF on timeout
    except Exception as e:
        error_msg = f"Unexpected error during CK execution for commit {commit_hash}: {e}"
        logger.error(error_msg, exc_info=True)
        if ck_temp_output_dir.exists():
            shutil.rmtree(ck_temp_output_dir)
        return pd.DataFrame() # Return empty DF on other errors


    # --- Process CK Output ---
    # CK might create files directly in the CWD or the provided path depending on version/flags.
    # Check both the specified temp dir and potentially the base dir if needed.
    class_csv_path = ck_temp_output_dir / 'class.csv'
    if not class_csv_path.exists():
         # Fallback check in case CK wrote outside the subdir (less likely with path specified)
         fallback_path = Path(str(ck_temp_output_dir).replace(f"temp_ck_{commit_hash}", "") + 'class.csv')
         if fallback_path.exists():
              logger.warning(f"CK output found at fallback path: {fallback_path}. Moving.")
              try:
                  shutil.move(str(fallback_path), class_csv_path)
              except Exception as move_err:
                   logger.error(f"Failed to move fallback CK output: {move_err}")
                   class_csv_path = None # Indicate failure to get the file
         else:
             logger.error(f"CK class output file not found at {class_csv_path} or fallback for commit {commit_hash}")
             class_csv_path = None


    metrics_df = pd.DataFrame()
    if class_csv_path and class_csv_path.exists():
        try:
            metrics_df = pd.read_csv(class_csv_path)
            logger.info(f"Successfully read {len(metrics_df)} CK metrics for commit {commit_hash}")
        except pd.errors.EmptyDataError:
             logger.warning(f"CK output file {class_csv_path} is empty for commit {commit_hash}.")
        except Exception as e:
             logger.error(f"Error reading CK output CSV {class_csv_path} for commit {commit_hash}: {e}")
    else:
        logger.error(f"Could not load CK metrics for commit {commit_hash}. CSV Path: {class_csv_path}")


    # Clean up temporary CK output directory
    if ck_temp_output_dir.exists():
        shutil.rmtree(ck_temp_output_dir)

    return metrics_df


def checkout_commit(repo: Repo, commit_hash: str) -> bool:
    """Checks out the repository at the specified commit. Returns True on success."""
    try:
        logger.debug(f"Checking out commit {commit_hash}...")
        # Clean state before checkout is crucial
        repo.git.reset('--hard')
        repo.git.clean('-fdx')
        repo.git.checkout(commit_hash, force=True)
        logger.debug(f"Checkout successful for {commit_hash}.")
        return True
    except GitCommandError as e:
        logger.error(f"Error checking out commit {commit_hash}: {e.stderr}")
        return False
    except Exception as e:
         logger.error(f"Unexpected error during checkout of {commit_hash}: {e}", exc_info=True)
         return False


def load_analyzed_commits(ck_output_dir: Path) -> Set[str]:
    """Loads analyzed commits by checking existing CSVs in the CK output folder."""
    analyzed = set()
    if not ck_output_dir.exists():
        ck_output_dir.mkdir(parents=True, exist_ok=True) # Ensure it exists
        return analyzed
    for filename in os.listdir(ck_output_dir):
        if filename.endswith('.csv'):
            commit_hash = filename.replace('.csv', '')
            analyzed.add(commit_hash)
    logger.info(f"Loaded {len(analyzed)} previously analyzed commits from {ck_output_dir}")
    return analyzed