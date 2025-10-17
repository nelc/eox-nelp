"""Programs API v1 Serializers."""
from rest_framework import serializers


class ProgramValidationMixin:
    """Mixin to add common validation methods for program serializers."""
    def validate_mandatory(self, value):
        """Validate mandatory field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(f"mandatory must be one of: {', '.join(valid_values)}")
        return value

    def validate_program_approve(self, value):
        """Validate program_approve field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(f"program_approve must be one of: {', '.join(valid_values)}")
        return value

    def validate_program_code(self, value):
        """Validate program_code field."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("program_code cannot be empty")
        return value.strip()


class ProgramsMetadataSerializer(serializers.Serializer, ProgramValidationMixin):  # pylint: disable=abstract-method
    """
    Serializer for programs metadata.

    This serializer handles the metadata for a specific course program.
    """
    trainer_type = serializers.IntegerField(default=10, read_only=True)
    type_of_activity = serializers.IntegerField()
    mandatory = serializers.CharField(max_length=2)
    program_approve = serializers.CharField(max_length=2)
    program_code = serializers.CharField(max_length=64)


class ProgramLookupSerializer(serializers.Serializer, ProgramValidationMixin):  # pylint: disable=abstract-method
    """
    DRF serializer for Program data, with methods for input validation.
    This serializer is designed to match the specific field names
    provided in the user's data object.
    """
    # Direct field mappings
    program_name = serializers.CharField(required=True)
    program_code = serializers.CharField(required=True)
    type_of_activity = serializers.CharField(required=True)
    type_of_activity_id = serializers.IntegerField(required=True)
    mandatory = serializers.CharField(required=True)
    program_approve = serializers.CharField(required=True)
    code = serializers.CharField(required=True)

    # Mapped fields to match the provided data
    date_start = serializers.CharField(required=True)
    date_end = serializers.CharField(required=True, allow_null=True)
    date_start_hijri = serializers.CharField(required=True)
    date_end_hijri = serializers.CharField(required=True, allow_null=True)
    duration = serializers.IntegerField(required=False)

    # Fields with fixed values, using read_only and default
    training_location = serializers.CharField(read_only=True, default="FutureX")
    trainer_type = serializers.IntegerField(read_only=True, default=10)
    unit = serializers.CharField(read_only=True, default="hour")

    certificate_url = serializers.SerializerMethodField()

    def get_certificate_url(self, program):
        """Generate certificate_url based on user and course code.
        Args:
            program: Program data dictionary.
        """
        if program.get("certificate_path"):
            return self.context["request"].build_absolute_uri(program["certificate_path"])
        return None
