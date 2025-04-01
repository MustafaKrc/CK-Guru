# worker/app/tasks/feature_extraction.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import Set
import pandas as pd
from git import Repo, GitCommandError
import logging
import tempfile

logger = logging.getLogger(__name__)
CK_JAR_PATH = Path('/app/third_party/ck.jar')

def run_ck_tool(repo_dir: Path, commit_hash: str) -> pd.DataFrame:
    """
    Runs the CK tool, handling its quirky output file naming by passing
    a file prefix within a temporary directory.

    Args:
        repo_dir: Path to the checked-out repository.
        commit_hash: The commit being analyzed.

    Returns:
        DataFrame containing the CK class metrics, or empty DataFrame on error.
    """
    use_jars = "false"
    max_files_per_partition = 0
    variables_and_fields = "false"
    metrics_df = pd.DataFrame()

    if not CK_JAR_PATH.exists():
        logger.error(f"CK JAR not found at {CK_JAR_PATH}")
        raise FileNotFoundError(f"CK JAR not found at {CK_JAR_PATH}")

    try:
        # Create a temporary directory to contain the uniquely prefixed output files
        with tempfile.TemporaryDirectory(prefix=f"ck_run_{commit_hash}_") as temp_dir_name:
            temp_dir_path = Path(temp_dir_name)
            logger.info(f"Using temporary directory for CK run: {temp_dir_path}")

            # --- Construct the FILE PREFIX for CK ---
            # Use a unique name within the temp dir to avoid collisions if CK somehow
            # ignores the full path part (less likely but safe)
            output_file_prefix = temp_dir_path / f"ck_output_{commit_hash}_"
            logger.info(f"Passing output prefix to CK: {output_file_prefix}")

            # --- Expected output file paths based on the prefix ---
            expected_class_csv_path = Path(f"{output_file_prefix}class.csv")
            expected_method_csv_path = Path(f"{output_file_prefix}method.csv") # And others if needed

            # --- Run CK with the output file prefix ---
            try:
                logger.info(f"Running CK for commit {commit_hash} on {repo_dir}...")
                command = [
                    'java', '-jar', str(CK_JAR_PATH), str(repo_dir),
                    use_jars, str(max_files_per_partition), variables_and_fields,
                    str(output_file_prefix) # <<< PASS THE PREFIX HERE
                ]
                logger.debug(f"Executing command: {' '.join(command)}")

                completed_process = subprocess.run(
                    command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200
                )
                logger.debug(f"CK stdout for {commit_hash}:\n{completed_process.stdout.decode()}")
                if completed_process.stderr:
                     # Log stderr but don't necessarily treat log4j warnings as errors
                     stderr_output = completed_process.stderr.decode()
                     if "Exception" in stderr_output or "Error" in stderr_output: # Look for actual errors
                         logger.error(f"CK stderr reported errors for {commit_hash}:\n{stderr_output}")
                     else:
                          logger.warning(f"CK stderr for {commit_hash}:\n{stderr_output}") # Likely just log4j noise

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
                 # Log specific errors
                if isinstance(e, subprocess.CalledProcessError):
                    error_msg = f"Error running CK (exit code {e.returncode}) for {commit_hash}: {e.stderr.decode()}"
                elif isinstance(e, subprocess.TimeoutExpired):
                    error_msg = f"CK timed out for commit {commit_hash}."
                else:
                    error_msg = f"Unexpected error during CK subprocess for {commit_hash}: {e}"
                logger.error(error_msg, exc_info=isinstance(e, Exception) and not isinstance(e, (subprocess.CalledProcessError, subprocess.TimeoutExpired)))
                return pd.DataFrame() # Temp dir cleaned by context manager

            # --- Process CK Output: Check for the prefixed file ---
            if expected_class_csv_path.is_file():
                logger.info(f"Found expected CK output file: {expected_class_csv_path}")
                try:
                    metrics_df = pd.read_csv(expected_class_csv_path)
                    logger.info(f"Successfully read {len(metrics_df)} CK metrics for {commit_hash}.")
                except pd.errors.EmptyDataError:
                     logger.warning(f"CK output file {expected_class_csv_path} is empty for {commit_hash}.")
                     metrics_df = pd.DataFrame()
                except Exception as e:
                     logger.error(f"Error reading CK output CSV {expected_class_csv_path} for {commit_hash}: {e}")
                     metrics_df = pd.DataFrame()
                finally:
                    # Clean up the specific output files manually since they might
                    # be directly in the temp dir now (TemporaryDirectory cleans the dir itself)
                    try:
                        if expected_class_csv_path.exists(): os.remove(expected_class_csv_path)
                        if expected_method_csv_path.exists(): os.remove(expected_method_csv_path)
                        # Remove other potential prefixed files (variable.csv etc.)
                    except OSError as rm_err:
                         logger.error(f"Error removing CK output files like {expected_class_csv_path}: {rm_err}")
            else:
                logger.error(f"CK class output file NOT found at expected path: {expected_class_csv_path}")
                # Check if maybe it DID create a directory despite the prefix (unlikely based on description)
                fallback_dir = Path(str(output_file_prefix)) # Check if a dir named like the prefix exists
                fallback_csv = fallback_dir / 'class.csv'
                if fallback_csv.is_file():
                     logger.error("CK created a DIRECTORY instead of using prefix! Trying to read from there.")
                     # Attempt to read from fallback (logic would be similar to above)
                     # metrics_df = pd.read_csv(fallback_csv) etc...
                # else: # No file found at all

        # --- Temporary directory is automatically cleaned up here ---
        logger.debug(f"Temporary directory {temp_dir_name} and its contents automatically cleaned up.")

    except Exception as outer_e:
        logger.error(f"Error during temporary directory handling for {commit_hash}: {outer_e}", exc_info=True)
        return pd.DataFrame()

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