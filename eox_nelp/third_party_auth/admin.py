"""
admin.py - Django admin site registrations and configurations.

This module defines the administrative interface for models related to
third-party authentication, enabling customization of how models are
presented and managed through the Django admin.

Admin classes defined here may customize behavior such as read-only fields,
custom save logic, field layouts, filters, and display settings.
"""
from django.contrib import admin

from eox_nelp.third_party_auth.models import SAMLBulkTemplateConfiguration


class SAMLBulkTemplateConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for the SAMLBulkTemplateConfiguration model.

    - Uses horizontal filter for `sites` to enhance selection UX.
    - Automatically assigns the current user to `changed_by` on save.
    - Prevents manual editing of `changed_by` by marking it as read-only.
    """
    filter_horizontal = ("sites",)
    readonly_fields = ("changed_by",)

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        """
        Customizes the form field for ManyToMany relationships in the admin.

        Specifically adds a warning message to the 'sites' field to inform
        administrators that removing a site should be done without making
        other changes. This is necessary because the model's `save()` is
        called before m2m changes are applied, which can lead to unintended
        updates to removed sites.

        Args:
            db_field (models.ManyToManyField): The field being processed.
            request (HttpRequest, optional): The current admin request.
            **kwargs: Additional keyword arguments for the form field.

        Returns:
            forms.Field: The customized form field.
        """
        if db_field.name == "sites":
            kwargs["help_text"] = (
                "⚠️ <strong>Warning:</strong> If you're going to remove a site, "
                "do it <em>without making any other changes</em> to the form. "
                "Otherwise, the site will still be updated during save."
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Overrides save_model to populate `changed_by` with the currently
        logged-in user whenever a SAMLBulkTemplateConfiguration is saved.
        """
        obj.changed_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(SAMLBulkTemplateConfiguration, SAMLBulkTemplateConfigurationAdmin)
