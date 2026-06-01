"""Unit tests for the course_experience.cache utilities.

This module verifies cache enablement flag handling and CRUD/merge
behaviour for experience cache helpers using patched cache and settings.
"""
import json
from unittest.mock import patch

from eox_nelp.course_experience import cache as cache_module


class TestCacheUtilities:
    """Test the cache utility functions for experience caching, including enablement flag and CRUD operations."""
    storage = {}

    def setup_method(self):
        """Setup common test data."""
        # pylint: disable=attribute-defined-outside-init
        self.kind = "feedback"
        self.user_id = 42
        self.target_id = "course-abc"
        self.key = cache_module.experience_cache_key(self.kind, self.user_id, self.target_id)
        self.storage.clear()  # reset fake cache storage before each test

    def fake_set(self, key, value, ttl=None):  # pylint: disable=unused-argument
        """Fake cache set method that stores values in a dict."""
        self.storage[key] = value

    def fake_get(self, key):
        """Fake cache get method that retrieves values from the dict."""
        return self.storage.get(key)

    def fake_delete(self, key):
        """Fake cache delete method that removes values from the dict."""
        self.storage.pop(key, None)

    @patch("eox_nelp.course_experience.cache.settings")
    def test_is_experience_cache_enabled_true_and_false(self, mock_settings):
        """Test that the cache enablement flag is correctly read from settings."""
        mock_settings.EOX_NELP_EXPERIENCE_CACHE_ENABLED = True
        assert cache_module.is_experience_cache_enabled() is True

        mock_settings.EOX_NELP_EXPERIENCE_CACHE_ENABLED = False
        assert cache_module.is_experience_cache_enabled() is False

    @patch("eox_nelp.course_experience.cache.cache")
    def test_set_get_delete_experience_cache(self, mock_cache):
        """Test that setting, getting, and deleting experience cache works as expected."""
        mock_cache.set.side_effect = self.fake_set
        mock_cache.get.side_effect = self.fake_get
        mock_cache.delete.side_effect = self.fake_delete

        value = {"rated": 5}
        cache_module.set_experience_cache(self.kind, self.user_id, self.target_id, value)
        # cache stores JSON string; get_experience_cache decodes it
        assert cache_module.get_experience_cache(self.kind, self.user_id, self.target_id) == value

        cache_module.delete_experience_cache(self.kind, self.user_id, self.target_id)
        assert cache_module.get_experience_cache(self.kind, self.user_id, self.target_id) is None

    @patch("eox_nelp.course_experience.cache.cache")
    def test_upsert_experience_cache_merges_values(self, mock_cache):
        """Test that upsert merges incoming values with existing cached object."""
        # pre-existing stored JSON
        existing = {"a": 1, "b": 2}
        self.storage[self.key] = json.dumps(existing)
        mock_cache.set.side_effect = self.fake_set
        mock_cache.get.side_effect = self.fake_get

        result = cache_module.upsert_experience_cache(self.kind, self.user_id, self.target_id, {"b": 20, "c": 3})

        assert result == {"a": 1, "b": 20, "c": 3}
        # stored value should be the merged JSON string
        assert json.loads(self.storage[self.key]) == result
