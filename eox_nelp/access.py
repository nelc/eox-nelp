"""Tenant access rules for the endpoints flagged by the 2026 pentest (C-001 cross-tenant lookups, M-001 public stats).

Every rule ships behind a waffle switch and starts LOG-ONLY: while its switch is off, the rule is evaluated and its
verdict is written into the caller audit line (see eox_nelp.audit) as `allow` or `would_deny`, and the request is
served as before. Once the switch is on (Django admin > Waffle > Switches, no deploy), a `deny` verdict refuses the
request. This lets the rules be sized from real traffic and rolled back instantly.

switches:
    ENFORCE_TENANT_SCOPED_LOOKUPS: user/certificate lookups are limited to the request tenant.
    ENFORCE_STATS_STAFF_ONLY: the stats page, the stats API and the public course feedback need a tenant staff user.

functions:
    has_global_lookup: Whether a user may look people up across every tenant.
    is_tenant_member: Whether a user belongs to the request site, with eox-core's own membership rule.
    get_tenant_orgs: The orgs of the request tenant.
    is_tenant_staff: Whether a user is staff of the request tenant.
    evaluate_rule: Record a rule verdict for the audit line and tell whether to refuse the request.

classes:
    TenantStaffOrLogOnly: DRF permission enforcing ENFORCE_STATS_STAFF_ONLY.
"""
from django.db.models import Q
from edx_toggles.toggles import WaffleSwitch
from eox_core.edxapp_wrapper.users import get_edxapp_user
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.edxapp_wrapper.student import CourseAccessRole

# .. toggle_name: eox_nelp.enforce_tenant_scoped_lookups
# .. toggle_implementation: WaffleSwitch
# .. toggle_default: False
# .. toggle_description: When on, the eox-nelp users API and certificates API only return people and certificates
#   of the request tenant, unless the caller has global lookup (superuser or GLOBAL_LOOKUP_GROUP). When off, the
#   verdict is only logged (`tenant_scope` in api_caller_audit).
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2026-10-21
# .. toggle_target_removal_date: 2027-01-31
ENFORCE_TENANT_SCOPED_LOOKUPS = WaffleSwitch("eox_nelp.enforce_tenant_scoped_lookups", __name__)

# .. toggle_name: eox_nelp.enforce_stats_staff_only
# .. toggle_implementation: WaffleSwitch
# .. toggle_default: False
# .. toggle_description: When on, the tenant stats page, the stats API and the public course feedback API require
#   a logged-in staff user of the request tenant. When off, the verdict is only logged (`stats_staff_only` in
#   api_caller_audit).
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2026-10-21
# .. toggle_target_removal_date: 2027-01-31
ENFORCE_STATS_STAFF_ONLY = WaffleSwitch("eox_nelp.enforce_stats_staff_only", __name__)

# Django group whose members (e.g. the service user of an integration's OAuth application) keep cross-tenant lookup.
# Managed in Django admin; the group does not need to exist until someone is added to it.
GLOBAL_LOOKUP_GROUP = "eox_nelp_global_lookup"

# Course access roles that make a user staff of a tenant (same set as the futurex-openedx-extensions dashboard views).
TENANT_STAFF_ROLES = ("staff", "instructor", "data_researcher", "org_course_creator_group")


def has_global_lookup(user):
    """Return whether the user may look people up across every tenant."""
    if not (user and user.is_authenticated):
        return False

    return user.is_superuser or user.groups.filter(name=GLOBAL_LOOKUP_GROUP).exists()


def is_tenant_member(user, site):
    """Return whether the user belongs to the site, using eox-core's configured user-origin sources."""
    try:
        get_edxapp_user(username=user.username, site=site)
    except NotFound:
        return False

    return True


def get_tenant_orgs():
    """Return the lowercased orgs of the request tenant."""
    return {org.lower() for org in configuration_helpers.get_current_site_orgs()}


def is_tenant_staff(user):
    """Return whether the user is platform staff or holds a staff course access role in an org of the tenant."""
    if not (user and user.is_authenticated):
        return False

    if user.is_superuser or user.is_staff:
        return True

    org_filter = Q()
    for org in get_tenant_orgs():
        org_filter |= Q(org__iexact=org)

    if not org_filter:
        return False

    return CourseAccessRole.objects.filter(org_filter, user=user, role__in=TENANT_STAFF_ROLES).exists()


def evaluate_rule(switch, rule, allowed, audit_extra):
    """Record the verdict of `rule` in `audit_extra` and return whether the request must be refused.

    The verdict is `allow`, `would_deny` (the rule fails but its switch is off) or `deny`.
    """
    enforced = switch.is_enabled()

    if allowed:
        audit_extra[rule] = "allow"
    else:
        audit_extra[rule] = "deny" if enforced else "would_deny"

    return enforced and not allowed


class TenantStaffOrLogOnly(BasePermission):
    """DRF permission: tenant staff only once ENFORCE_STATS_STAFF_ONLY is on; logs the verdict either way."""

    def has_permission(self, request, view):
        """Evaluate the stats rule; refuse only when it fails and is enforced."""
        audit_extra = getattr(view, "audit_extra", {})

        return not evaluate_rule(
            ENFORCE_STATS_STAFF_ONLY, "stats_staff_only", is_tenant_staff(request.user), audit_extra,
        )
