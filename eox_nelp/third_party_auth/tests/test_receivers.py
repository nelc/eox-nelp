"""
Tests for receivers defined in eox_nelp.third_party_auth.receivers.

This module verifies that signal receivers behave correctly when triggered
by changes in associated models or fields.
"""
from unittest.mock import MagicMock, patch

from django.contrib.sites.models import Site
from django.test import TestCase

from eox_nelp.third_party_auth.models import SAMLBulkTemplateConfiguration
from eox_nelp.third_party_auth.receivers import apply_sites_when_m2m_changes


class TestApplySitesWhenM2MChanges(TestCase):
    """Tests for the apply_sites_when_m2m_changes receiver."""

    @patch("eox_nelp.third_party_auth.receivers.Site.objects.filter")
    def test_post_add_action_triggers_apply_to_sites(self, mock_site_filter):
        """Test apply_sites_when_m2m_changes with 'post_add' action.

        Expected behavior:
            - Site.objects.filter is called with the pk_set.
            - apply_to_sites is called with the resulting sites.
        """
        mock_site_1 = MagicMock(spec=Site)
        mock_site_2 = MagicMock(spec=Site)
        mock_sites = [mock_site_1, mock_site_2]
        mock_site_filter.return_value = mock_sites

        instance = MagicMock(spec=SAMLBulkTemplateConfiguration)
        action = "post_add"
        pk_set = {1, 2}

        apply_sites_when_m2m_changes(
            sender=None,
            instance=instance,
            action=action,
            pk_set=pk_set,
        )

        mock_site_filter.assert_called_once_with(pk__in=pk_set)
        instance.apply_to_sites.assert_called_once_with(mock_sites)

    @patch("eox_nelp.third_party_auth.receivers.Site.objects.filter")
    def test_non_post_add_action_does_nothing(self, mock_site_filter):
        """Test apply_sites_when_m2m_changes with action other than 'post_add'.

        Expected behavior:
            - Site.objects.filter is not called.
            - apply_to_sites is not called.
        """
        instance = MagicMock(spec=SAMLBulkTemplateConfiguration)
        action = "post_remove"
        pk_set = {1, 2}

        apply_sites_when_m2m_changes(
            sender=None,
            instance=instance,
            action=action,
            pk_set=pk_set,
        )

        mock_site_filter.assert_not_called()
        instance.apply_to_sites.assert_not_called()
