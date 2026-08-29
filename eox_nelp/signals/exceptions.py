"""Exceptions for the signals module.

Classes:
    MTTrainingStageError: Raised when the Minister of Tourism API does not acknowledge an update.
"""


class MTTrainingStageError(Exception):
    """Raised when the Minister of Tourism API answers with a non success response code."""
