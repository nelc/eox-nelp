"""Utility functions for caching user experience data (likes, feedback, reports) in Django cache framework."""
import json

from django.conf import settings
from django.core.cache import cache


def is_experience_cache_enabled():
    """Check if experience caching is enabled via Django settings."""
    return getattr(settings, "EOX_NELP_EXPERIENCE_CACHE_ENABLED", False)


def experience_cache_key(kind, user_id, target_id):
    """
    kind: 'like', 'feedback', 'report', etc.
    target_id: item_id or course_id (string or int)
    """
    return f"experience:{kind}:{user_id}:{target_id}"


def set_experience_cache(kind, user_id, target_id, value):
    """Set experience data in cache."""
    cache.set(
        experience_cache_key(kind, user_id, target_id),
        json.dumps(value),
        getattr(settings, "EOX_NELP_EXPERIENCE_CACHE_TTL", 7200),  # 2 hours default
    )


def get_experience_cache(kind, user_id, target_id):
    """Get experience data from cache."""
    val = cache.get(experience_cache_key(kind, user_id, target_id))
    return json.loads(val) if val is not None else None


def delete_experience_cache(kind, user_id, target_id):
    """Delete experience data from cache."""
    cache.delete(experience_cache_key(kind, user_id, target_id))
