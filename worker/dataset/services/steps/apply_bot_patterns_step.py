# worker/dataset/services/steps/apply_bot_patterns_step.py
import logging
import re
import pandas as pd

from services.context import DatasetContext
from services.interfaces import IDatasetGeneratorStep
from shared.repositories.bot_pattern_repository import BotPatternRepository
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class ApplyBotPatternsStep(IDatasetGeneratorStep):
    """
    Applies bot filtering to the dataset based on global and repository-specific regex patterns.
    """
    name = "Apply Bot Patterns"

    def execute(
        self,
        context: DatasetContext,
        *,
        bot_pattern_repo: BotPatternRepository,
        **kwargs,
    ) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.dataframe is None or context.dataframe.empty:
            step_logger.warning("DataFrame is empty, skipping bot pattern application.")
            return context

        step_logger.info("Fetching bot patterns from database...")
        patterns, _ = bot_pattern_repo.get_bot_patterns(
            repository_id=context.repository_id, include_global=True
        )

        if not patterns:
            step_logger.info("No bot patterns found. Skipping filtering.")
            return context

        step_logger.info(f"Applying {len(patterns)} bot patterns...")
        
        inclusions = [re.compile(p.pattern) for p in patterns if not p.is_exclusion]
        exclusions = [re.compile(p.pattern) for p in patterns if p.is_exclusion]
        
        step_logger.debug(f"Inclusion patterns: {len(inclusions)}, Exclusion patterns: {len(exclusions)}")
        
        def is_bot(author_name: str) -> bool:
            if not isinstance(author_name, str):
                return False
            
            # If any exclusion pattern matches, it's NOT a bot.
            if any(exc.search(author_name) for exc in exclusions):
                return False
            
            # If any inclusion pattern matches (and no exclusion did), it IS a bot.
            if any(inc.search(author_name) for inc in inclusions):
                return True
            
            return False

        original_rows = len(context.dataframe)
        
        # Apply the filter logic
        bot_mask = context.dataframe['author_name'].apply(is_bot)
        context.dataframe = context.dataframe[~bot_mask]

        rows_removed = original_rows - len(context.dataframe)
        if rows_removed > 0:
            step_logger.info(f"Removed {rows_removed} commits from bot authors.")
        else:
            step_logger.info("No commits matched the bot patterns.")

        return context