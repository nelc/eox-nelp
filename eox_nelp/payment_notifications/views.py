"""
Payment Notifications views
"""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from edx_django_utils.db.read_replica import use_read_replica_if_available

from eox_nelp.edxapp_wrapper.edxmako import edxmako
from eox_nelp.payment_notifications.models import PaymentNotification


@method_decorator(login_required, name='dispatch')
class PaymentNotificationsView(View):
    """
    Display a PaymentNotification for users that navigate to /payment-notifications
    """

    def get(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Checks whether payment notifications are enabled in the system configuration
        before displaying the payment notifications page. If payment notifications
        are not enabled, it raises an Http404 response.

        Args:
            request (HttpRequest): The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: An HTTP response that renders the "payment_notifications_with_frame.html"
            template within the current context.

        Raises:
            Http404: If payment notifications are not enabled in the configuration.
        """

        if not getattr(settings, "ENABLE_PAYMENT_NOTIFICATIONS", None):
            raise Http404

        return edxmako.shortcuts.render_to_response("payment_notifications_with_frame.html", {}, "main", request)


def get_payment_notifications_context(request):
    """
    Calculate the notifications for a user.
    """
    default_context = {
        "payment_notifications": [],
    }

    if not getattr(settings, "ENABLE_PAYMENT_NOTIFICATIONS", None):
        return default_context

    user_id = request.user.id

    # count the views that belong to real users looking at their dashboard or notifications view
    count_view = False
    count_in_paths = [
        '/dashboard',
        '/eox-nelp/payment-notifications',
    ]
    if any(x in request.path for x in count_in_paths):
        count_view = True
    else:
        # if the view is not part in the list we dont really need to do any query
        return default_context

    # allows staff users to masquerade to debug issues
    if request.GET.get("showpaymentnotificationsforuser", False) and request.user.is_staff:
        user_id = request.GET.get("showpaymentnotificationsforuser", user_id)
        count_view = False

    all_notifications_for_user = use_read_replica_if_available(
        PaymentNotification.objects.filter(  # pylint: disable=no-member
            cdtrans_lms_user_id=user_id,
        ),
    ),
    if count_view:
        for notification in all_notifications_for_user:
            notification.internal_view_count += 1
            notification.save()

    context = {
        "payment_notifications": all_notifications_for_user,
    }
    return context
