"""This file contains all the test for the stats views.py file.

Classes:
    GetTenantStatsTestCase: Test get_tenant_stats function based view.
"""
from ddt import data, ddt
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status

from eox_nelp.stats.views import STATS_QUERY_PARAMS


@ddt
class GetTenantStatsTestCase(TestCase):
    """ Test get_tenant_stats function based view."""

    def setUp(self):
        """
        Set base variables and objects across experience test cases.
        """
        self.client = Client()
        self.template_name = "tenant_stats/index.html"

    def test_get_default_stats(self):
        """
        Test that the default behavior, that is just render the tenant-stats div

        Expected behavior:
            - Status code 200.
            - template name is as expected.
            - tenant-stats div exist
        """
        url_endpoint = reverse("stats:tenant")

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.template_name, response.templates[0].name)
        self.assertContains(response, '<div id="tenant-stats"></div')

        for query_param in STATS_QUERY_PARAMS:
            self.assertEqual("true", response.context[query_param])

    @data(*STATS_QUERY_PARAMS)
    def test_filter_stat_out(self, query_param):
        """
        Since the default behavior shows all the components this tests that specific component
        is filtered out when the query param is false.

        Expected behavior:
            - Status code 200.
            - template name is as expected.
            - tenant-stats div exist
            - the query param is 'false'
            - CSS was included
            - JS was included
        """
        url_endpoint = f"{reverse('stats:tenant')}?{query_param}=false"

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.template_name, response.templates[0].name)
        self.assertContains(response, '<div id="tenant-stats"></div')
        self.assertEqual("false", response.context[query_param])
        self.assertContains(response, "tenant_stats/css/tenant_stats.css")
        self.assertContains(response, "tenant_stats/js/tenant_stats.js")

    @data(*STATS_QUERY_PARAMS)
    def test_flag_value_is_never_reflected(self, query_param):
        """
        A flag whose value is neither "true" nor "false" must be coerced, never
        rendered verbatim, so the query params cannot be used as a reflected-XSS sink.

        Expected behavior:
            - Status code 200.
            - the context value is the literal "false" (not the attacker string).
            - the attacker payload does not appear anywhere in the response body.
        """
        payload = '"</script><img src=x onerror=alert(1)>'
        url_endpoint = f"{reverse('stats:tenant')}?{query_param}={payload}"

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("false", response.context[query_param])
        self.assertNotIn("onerror=alert(1)", response.content.decode("utf-8"))

    def test_unknown_query_params_are_ignored(self):
        """
        Only the known STATS_QUERY_PARAMS reach the context; arbitrary query params
        supplied by the caller must not be copied into the render context.

        Expected behavior:
            - Status code 200.
            - the unknown param key is absent from the context.
        """
        url_endpoint = f"{reverse('stats:tenant')}?evil=1&another=2"

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertNotIn("evil", response.context)
        self.assertNotIn("another", response.context)
