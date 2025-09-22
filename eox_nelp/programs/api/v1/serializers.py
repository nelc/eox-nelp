"""Programs API v1 Serializers."""
from rest_framework import serializers


class ProgramValidationMixin:
    """Mixin to add common validation methods for program serializers."""
    # pylint: disable=invalid-name
    def validate_Mandatory(self, value):
        """Validate Mandatory field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(f"Mandatory must be one of: {', '.join(valid_values)}")
        return value

    def validate_Program_ABROVE(self, value):
        """Validate Program_ABROVE field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(f"Program_ABROVE must be one of: {', '.join(valid_values)}")
        return value

    def validate_Program_code(self, value):
        """Validate Program_code field."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Program_code cannot be empty")
        return value.strip()


class ProgramsMetadataSerializer(serializers.Serializer, ProgramValidationMixin):  # pylint: disable=abstract-method
    """
    Serializer for programs metadata.

    This serializer handles the metadata for a specific course program.
    """
    # This is for use DRF logic of validation, but the fields or the API are very rare in shape.
    trainer_type = serializers.IntegerField(default=10, read_only=True)
    Type_of_Activity = serializers.IntegerField()
    Mandatory = serializers.CharField(max_length=2)
    Program_ABROVE = serializers.CharField(max_length=2)
    Program_code = serializers.CharField(max_length=64)


class ProgramLookupSerializer(serializers.Serializer, ProgramValidationMixin):  # pylint: disable=abstract-method
    """
    DRF serializer for Program data, with methods for input validation.
    This serializer is designed to match the specific field names
    provided in the user's data object.
    """
    # Direct field mappings
    Program_name = serializers.CharField(required=True)
    Program_code = serializers.CharField(required=True)
    Type_of_Activity = serializers.CharField(required=True)
    Type_of_Activity_id = serializers.IntegerField(required=True)
    Mandatory = serializers.CharField(required=True)
    Program_ABROVE = serializers.CharField(required=True)
    Code = serializers.CharField(required=True)

    # Mapped fields to match the provided data
    Date_Start = serializers.CharField(required=True)
    Date_End = serializers.CharField(required=True, allow_null=True)
    Date_Start_Hijri = serializers.CharField(required=True)
    Date_End_Hijri = serializers.CharField(required=True, allow_null=True)
    duration = serializers.IntegerField(required=False)

    # Fields with fixed values, using read_only and default
    Training_location = serializers.CharField(read_only=True, default="FutureX")
    Trainer_type = serializers.IntegerField(read_only=True, default=10)
    Unit = serializers.CharField(read_only=True, default="hour")
