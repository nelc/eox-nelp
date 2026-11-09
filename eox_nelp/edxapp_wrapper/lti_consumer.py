"""Wrapper of the xblock-lti-consumer app.

Attributes:
    backend: Imported module by using the plugin settings.
    LtiAgsScore: The model of the LTI Advantage (AGS) scores the tools post.
    get_user_from_external_user_id: User of an LTI `sub` (external user id), or None when unknown.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_LTI_CONSUMER_BACKEND)

LtiAgsScore = backend.get_lti_ags_score_model()
get_user_from_external_user_id = backend.get_user_from_external_user_id
