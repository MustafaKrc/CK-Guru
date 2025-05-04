# shared/utils/pipeline_logging.py
import logging

class StepLogger:
    """Simple wrapper to add a prefix to log messages."""
    def __init__(self, logger: logging.Logger, log_prefix: str):
        self.logger = logger
        self.log_prefix = log_prefix

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(f"{self.log_prefix} {msg}", *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(f"{self.log_prefix} {msg}", *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(f"{self.log_prefix} {msg}", *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(f"{self.log_prefix} {msg}", *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(f"{self.log_prefix} {msg}", *args, **kwargs)