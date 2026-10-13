"""eox-nelp version of eox-core's `EdxappEnrollment` (POST /eox-core/api/v1/enrollment/).

Differs from eox-core in `post` (caps, request id), `prepare_multiresponse` (same batch loop, our
serializer) and `single_enrollment_create` (delegates to `EnrollmentService`). GET/PUT/DELETE are
inherited untouched. `prepare_multiresponse` mirrors eox-core's rules (200, or 202 when any item
errored); tests/test_pins.py fails if eox-core's copy ever behaves differently.
"""
import re
import uuid

from django.contrib.sites.shortcuts import get_current_site
from eox_core.api.v1.views import EdxappEnrollment as CoreEdxappEnrollment
from eox_core.api.v1.views import audit_drf_api
from eox_core.edxapp_wrapper.users import get_edxapp_user
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from eox_nelp.enrollment_api.caps import check_caps
from eox_nelp.enrollment_api.serializers import NelpEnrollmentQuerySerializer
from eox_nelp.enrollment_api.services import CallContext, EnrollmentService

REQUEST_ID_HEADER = "X-Request-ID"
SAFE_REQUEST_ID = re.compile(r"[\w.-]{1,64}")  # caller-supplied ids end up in log lines


def caller_id(request):
    """Who is calling: the OAuth application when there is one, otherwise the authenticated user."""
    application = getattr(request.auth, "application", None)
    if application is not None:
        return f"app-{application.client_id}"
    return f"user-{request.user.pk}"


class NelpEdxappEnrollment(CoreEdxappEnrollment):
    """Enrollment endpoint that also reserves enrollments for emails without an account."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = None
        self.batch_index = 0

    @audit_drf_api(
        action='Create single or bulk enrollments',
        data_filter=['email', 'username', 'course_id', 'mode', 'is_active', 'enrollment_attributes'],
        method_name='eox_core_api_method',
    )
    def post(self, request, *args, **kwargs):
        """Reject over-cap calls, then run the batch loop; echo the request id."""
        data = request.data
        check_caps(caller_id(request), len(data) if isinstance(data, list) else 1)
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if SAFE_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        site = getattr(request, "site", None) or get_current_site(request)
        self.service = EnrollmentService(
            CallContext(request_id, caller_id(request), site.id, site.domain),
            find_user=lambda item: get_edxapp_user(**self.get_user_query(None, query_params=item)),
            enroll_account=super().single_enrollment_create,
        )
        self.batch_index = 0
        response = self.prepare_multiresponse(data, self.single_enrollment_create)
        response[REQUEST_ID_HEADER] = request_id
        return response

    def single_enrollment_create(self, *args, **kwargs):
        """Handle one item through the service (called by eox-core's `prepare_multiresponse`)."""
        index, self.batch_index = self.batch_index, self.batch_index + 1
        return self.service.enroll(kwargs, index)

    @staticmethod
    def prepare_multiresponse(request_data, action_method):
        """eox-core's batch loop with `NelpEnrollmentQuerySerializer`: item errors do not stop the batch."""
        many = isinstance(request_data, list)
        serializer = NelpEnrollmentQuerySerializer(data=request_data, many=many)
        serializer.is_valid(raise_exception=True)
        queries = serializer.validated_data if many else [serializer.validated_data]

        responses, failed = [], False
        for query in queries:
            try:
                result = action_method(**query)
                responses += result if isinstance(result, list) else [result]
            except APIException as error:
                failed = True
                responses.append({**query, "error": {"detail": error.detail}})

        body = responses if many or "bundle_id" in request_data else responses[0]
        return Response(body, status=status.HTTP_202_ACCEPTED if failed else status.HTTP_200_OK)
