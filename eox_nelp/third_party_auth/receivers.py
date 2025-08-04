"""
Signal handlers for reacting to changes in the SAMLBulkTemplateConfiguration model.

This module ensures that when new Sites are added to a SAMLBulkTemplateConfiguration,
the corresponding SAMLConfiguration and ProviderConfiguration instances are created
or updated accordingly.
"""

from django.contrib.sites.models import Site
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from eox_nelp.third_party_auth.models import SAMLBulkTemplateConfiguration


@receiver(m2m_changed, sender=SAMLBulkTemplateConfiguration.sites.through)  # pylint: disable=no-member
def apply_sites_when_m2m_changes(sender, instance, action, pk_set, **kwargs):  # pylint: disable=unused-argument
    """
    Signal handler triggered when the 'sites' ManyToMany field is modified.

    This only reacts to 'post_add' events, meaning when new sites are added
    to the SAMLBulkTemplateConfiguration. It applies the configuration template
    to the newly added sites.

    Note: This avoids applying to removed sites or during form saves, ensuring
    consistency with the main model save behavior.

    Args:
        sender (Model): The intermediate model managing the M2M relationship.
        instance (SAMLBulkTemplateConfiguration): The template instance being modified.
        action (str): The type of change. Only 'post_add' is handled.
        pk_set (set): Primary keys of the affected Site instances.
        **kwargs: Additional keyword arguments.
    """
    if action == "post_add":
        new_sites = Site.objects.filter(pk__in=pk_set)
        instance.apply_to_sites(new_sites)
