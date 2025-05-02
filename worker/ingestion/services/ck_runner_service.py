# worker/ingestion/services/ck_runner_service.py
import logging
import os
import tempfile
import subprocess
from pathlib import Path
import pandas as pd

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Define path relative to the service file or use an absolute path based on deployment
# Assuming Dockerfile places it at /app/third_party/ck.jar
CK_JAR_PATH = Path('/app/third_party/ck.jar')

class CKRunnerService:
    """Encapsulates the logic for running the CK metric tool."""

    def __init__(self):
        if not CK_JAR_PATH.is_file():
            msg = f"CK JAR not found at configured path: {CK_JAR_PATH}"
            logger.error(msg)
            # Decide if this should be a fatal error during service instantiation
            raise FileNotFoundError(msg)
        logger.debug("CKRunnerService initialized.")

    def run(self, repo_dir: Path, commit_hash: str) -> pd.DataFrame:
        """
        Runs the CK tool for a specific commit in the given repository directory.

        Args:
            repo_dir: Path to the checked-out repository.
            commit_hash: The commit being analyzed (used for temporary file naming).

        Returns:
            DataFrame containing the CK class metrics, or empty DataFrame on error.
        """
        # Default CK tool parameters (can be made configurable if needed)
        use_jars = "false"
        max_files_per_partition = 0
        variables_and_fields = "false"
        metrics_df = pd.DataFrame()

        try:
            # Use a temporary directory for CK's output files
            with tempfile.TemporaryDirectory(prefix=f"ck_run_{commit_hash}_") as temp_dir_name:
                temp_dir_path = Path(temp_dir_name)
                # CK expects a file *prefix*, not a directory path for output
                output_file_prefix = temp_dir_path / f"ck_output_{commit_hash}_"
                expected_class_csv_path = temp_dir_path / f"ck_output_{commit_hash}_class.csv"

                # Construct and run the command
                command = [
                    'java', '-jar', str(CK_JAR_PATH), str(repo_dir),
                    use_jars, str(max_files_per_partition), variables_and_fields,
                    str(output_file_prefix) # Pass the prefix
                ]
                logger.debug(f"Executing CK command: {' '.join(command)}")

                try:
                    completed_process = subprocess.run(
                        command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, encoding='utf-8', errors='ignore', # Add text=True
                        timeout=1200 # Keep timeout
                    )
                    # Log stderr cautiously, filtering common Java/log4j noise
                    if completed_process.stderr:
                        stderr_output = completed_process.stderr.strip()
                        if stderr_output and "log4j" not in stderr_output.lower():
                            logger.warning(f"CK stderr for {commit_hash[:7]}:\n{stderr_output}")

                except subprocess.TimeoutExpired:
                    logger.error(f"CK tool timed out for commit {commit_hash[:7]} at path {repo_dir}")
                    return pd.DataFrame() # Return empty on timeout
                except subprocess.CalledProcessError as e:
                    logger.error(f"CK tool failed (exit code {e.returncode}) for commit {commit_hash[:7]} at path {repo_dir}.\nStderr: {e.stderr}")
                    return pd.DataFrame() # Return empty on error
                except Exception as e:
                     logger.error(f"Unexpected error running CK tool for commit {commit_hash[:7]}: {e}", exc_info=True)
                     return pd.DataFrame()

                # Process the output file
                if expected_class_csv_path.is_file():
                    try:
                        metrics_df = pd.read_csv(expected_class_csv_path)
                    except pd.errors.EmptyDataError:
                        logger.warning(f"CK output file {expected_class_csv_path.name} was empty for {commit_hash[:7]}.")
                        metrics_df = pd.DataFrame()
                    except Exception as e:
                        logger.error(f"Error reading CK output CSV {expected_class_csv_path.name} for {commit_hash[:7]}: {e}")
                        metrics_df = pd.DataFrame()
                    # Optional: Clean up files immediately if needed, though temp dir handles it
                else:
                    logger.error(f"CK class output file not found at expected path: {expected_class_csv_path}")

        except Exception as outer_e:
            # Catch errors related to temp directory creation/cleanup
            logger.error(f"Error during CK temporary directory handling for {commit_hash[:7]}: {outer_e}", exc_info=True)
            return pd.DataFrame()

        return metrics_df

# --- Create a singleton instance for potential reuse ---
# Note: If state is ever added, remove the singleton pattern

ck_runner_service = CKRunnerService()