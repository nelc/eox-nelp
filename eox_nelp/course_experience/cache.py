from django.core.cache import cache
from django.conf import settings
import json

CACHE_TTL = getattr(settings, "EOX_NELP_EXPERIENCE_CACHE_TTL", 7200)  # 2 hours default

def experience_key(kind, user_id, target_id):
    """
    kind: 'like', 'feedback', 'report', etc.
    target_id: item_id or course_id (string or int)
    """
    return f"experience:{kind}:{user_id}:{target_id}"

def set_experience(kind, user_id, target_id, value):
    """Set experience data in cache."""
    cache.set(experience_key(kind, user_id, target_id), json.dumps(value), CACHE_TTL)

def get_experience(kind, user_id, target_id):
    """Get experience data from cache."""
    val = cache.get(experience_key(kind, user_id, target_id))
    return json.loads(val) if val is not None else None

def delete_experience(kind, user_id, target_id):
    """Delete experience data from cache."""
    cache.delete(experience_key(kind, user_id, target_id))
