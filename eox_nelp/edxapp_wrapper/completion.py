"""Wrapper of the edx-completion app.

Attributes:
    backend: Imported module by using the plugin settings.
    BlockCompletion: The BlockCompletion model (its manager has `submit_completion`).
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_COMPLETION_BACKEND)

BlockCompletion = backend.get_block_completion_model()
