"""This file contains all the test for the stats decorator.py file.

Classes:
    TestCacheMethod: Tests cases for cache_method decorator.
"""
import unittest

from django.core.cache import cache
from mock import Mock

from eox_nelp.stats.decorators import cache_method


class TestCacheMethod(unittest.TestCase):
    """Tests cases for cache_method decorator."""

    def tearDown(self):
        """Clear cache after every test to keep standard conditions"""
        cache.clear()

    def test_empty_cache(self):
        """Test when the cached response is not found.

        Expected behavior:
            - Result contains expected value
            - Test function was called with the right parameter.
            - Cache was set
        """
        test_function = Mock()
        test_function.__name__ = "test_function"
        test_function.return_value = {"test": True}
        arg = "I do nothing"

        wrapper = cache_method(test_function)
        result = wrapper(arg)

        self.assertTrue(result["test"])
        test_function.assert_called_once_with(arg)
        self.assertTrue(cache.get("test_function.I do nothing.STATS_CACHE_KEY"))

    def test_cache_found(self):
        """Test when the cached response is found.

        Expected behavior:
            - Result contains expected value
            - Test function was not called again.
        """
        expected_value = {"cache_found": True}
        cache.set("test_function.I do nothing.STATS_CACHE_KEY", expected_value)
        test_function = Mock()
        test_function.__name__ = "test_function"
        arg = "I do nothing"

        wrapper = cache_method(test_function)
        result = wrapper(arg)

        self.assertTrue(result["cache_found"])
        test_function.assert_not_called()
