"""
Test integration file.
"""
from unittest import TestCase

import requests
from rest_framework import status

from eox_nelp.tests.integration.constants import LMS_BASE_URL


class TestInfoView(TestCase):
    """
    Integration test suite for the info view.
    """

    def test_info_view_success(self) -> None:
        """Test the info view.

        Expected result:
        - The status code is 200.
        - The response contains the version, name and git commit hash.
        """
        url = f"{LMS_BASE_URL}/eox-nelp/eox-info/"

        response = requests.get(url, timeout=5)

        response_data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("version", response_data)
        self.assertIn("name", response_data)
        self.assertIn("git", response_data)
