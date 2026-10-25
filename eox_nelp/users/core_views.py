"""eox-nelp version of eox-core's `EdxappUser` (POST /eox-core/api/v1/user/).

eox-core's create path ends in edx-platform's `do_create_account`, which reports rejected fields
(invalid username, national_id already registered, a missing registration field) as Django's core
`ValidationError`. DRF turns only its own exceptions into responses, so callers got an opaque 500
and the field errors reached only the LMS log. Here they become a 400 carrying the per-field
messages, which is what eox-core's own docstring promises. Everything else is inherited.
"""
from functools import wraps

from django.core.exceptions import ValidationError as DjangoValidationError
from eox_core.api.v1.views import EdxappUser as CoreEdxappUser
from rest_framework.exceptions import ValidationError


class NelpEdxappUser(CoreEdxappUser):
    """Create-user endpoint whose rejected fields answer 400 instead of 500."""

    @wraps(CoreEdxappUser.post)  # keeps eox-core's API docs schema and docstring
    def post(self, request, *args, **kwargs):
        """eox-core's create (audit record included), with Django validation errors as a 400."""
        try:
            return super().post(request, *args, **kwargs)
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "error_dict") else error.messages
            raise ValidationError(detail) from error
