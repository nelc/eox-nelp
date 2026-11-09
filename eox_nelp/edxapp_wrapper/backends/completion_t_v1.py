"""Backend for the edx-completion app.
This file contains all the necessary completion dependencies from
https://github.com/openedx/completion/blob/master/completion/models.py
"""
from completion.models import BlockCompletion  # pylint: disable=import-error


def get_block_completion_model():
    """Allow to get the BlockCompletion model.

    Returns:
        BlockCompletion model.
    """
    return BlockCompletion
